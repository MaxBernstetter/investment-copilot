"""The quality check job end to end: persistence reads in, a recorded check out. No Oracle."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import httpx
import oracledb
import pytest
from contracts.persistence import v1
from opentelemetry.sdk.metrics.export import HistogramDataPoint, NumberDataPoint
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode, format_span_id, format_trace_id
from pydantic import SecretStr

from processing.application.ports import QualityStore
from processing.config import DatabaseSettings
from processing.domain.assessment import QualityCheck
from processing.domain.quality import Rule, Status
from processing.infrastructure.metrics import (
    CHECK_DURATION,
    METRIC_NAMES,
    QUALITY_CHECKS,
    QUALITY_FINDINGS,
    VALUES_CHECKED,
)
from processing.infrastructure.proc import OracleQualityStore
from processing.infrastructure.telemetry import Telemetry
from processing.job import main, oracle_quality_store
from tests.unit.fakes import RecordingMetricExporter, job_telemetry

URL = "http://persistence.test:8001"
CHECKED_AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
CURVE_ID = "ecb-aaa-spot-sim"
FROM = date(2026, 10, 5)
TO = date(2026, 10, 8)

MONTHS = {
    "3M": 3,
    "6M": 6,
    "1Y": 12,
    "2Y": 24,
    "3Y": 36,
    "5Y": 60,
    "7Y": 84,
    "10Y": 120,
    "15Y": 180,
    "20Y": 240,
    "30Y": 360,
}

BASE_CURVE = {
    "3M": Decimal("1.95"),
    "6M": Decimal("1.93"),
    "1Y": Decimal("1.90"),
    "2Y": Decimal("1.95"),
    "3Y": Decimal("2.02"),
    "5Y": Decimal("2.18"),
    "7Y": Decimal("2.36"),
    "10Y": Decimal("2.61"),
    "15Y": Decimal("2.86"),
    "20Y": Decimal("2.98"),
    "30Y": Decimal("3.01"),
}


@dataclass
class Run:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def summary(self) -> dict[str, object]:
        result: dict[str, object] = json.loads(self.stdout)
        return result


class RecordingStore(QualityStore):
    def __init__(self) -> None:
        self.checks: list[QualityCheck] = []

    async def record(self, check: QualityCheck) -> None:
        self.checks.append(check)


def _curve_after_bad_value() -> dict[tuple[str, date], tuple[float, int]]:
    """Published state after the corrected-yield events publish, gap and bad-value."""
    observations: dict[tuple[str, date], tuple[float, int]] = {}
    version_id = 0

    def add(
        day: date,
        shift: str,
        *,
        without: frozenset[str] = frozenset(),
        overrides: dict[str, str] | None = None,
    ) -> None:
        nonlocal version_id
        absolute = {maturity: Decimal(value) for maturity, value in (overrides or {}).items()}
        for maturity, base in BASE_CURVE.items():
            if maturity in without:
                continue
            version_id += 1
            value = absolute.get(maturity, base + Decimal(shift))
            observations[(maturity, day)] = (float(value), version_id)

    add(date(2026, 10, 5), "0.00")
    add(date(2026, 10, 6), "0.01")
    add(date(2026, 10, 7), "0.02", without=frozenset({"10Y", "30Y"}))
    add(date(2026, 10, 8), "0.03", overrides={"10Y": "26.40"})
    return observations


def _curve_after_correction() -> dict[tuple[str, date], tuple[float, int]]:
    """The bad-value state, then the gap filled and the bad 10Y value corrected in new versions."""
    observations = _curve_after_bad_value()
    version_id = max(version for _, version in observations.values())
    for key, value in (
        (("10Y", date(2026, 10, 7)), 2.63),
        (("30Y", date(2026, 10, 7)), 3.03),
        (("10Y", date(2026, 10, 8)), 2.64),
    ):
        version_id += 1
        observations[key] = (value, version_id)
    return observations


def _transport(observations: dict[tuple[str, date], tuple[float, int]]) -> httpx.MockTransport:
    latest_day = max(valid_date for _, valid_date in observations)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return httpx.Response(405)
        path = request.url.path
        if path == v1.CURVE_OBSERVATIONS_PATH.format(curve_id=CURVE_ID):
            points = []
            for maturity in BASE_CURVE:
                key = (maturity, latest_day)
                if key not in observations:
                    points.append(
                        v1.CurvePoint(
                            maturity=maturity,
                            months=MONTHS[maturity],
                            value=None,
                            version_id=None,
                        )
                    )
                    continue
                value, version_id = observations[key]
                points.append(
                    v1.CurvePoint(
                        maturity=maturity,
                        months=MONTHS[maturity],
                        value=value,
                        version_id=version_id,
                    )
                )
            curve_body = v1.CurveObservationsResponse(
                data=v1.CurveObservations(
                    curve_id=CURVE_ID,
                    valid_date=latest_day,
                    points=points,
                ),
                meta=v1.CurveMeta(as_of=CHECKED_AS_OF),
            )
            return httpx.Response(200, json=curve_body.model_dump(mode="json"))

        prefix = f"/v1/curves/{CURVE_ID}/maturities/"
        if path.startswith(prefix) and path.endswith("/observations"):
            maturity = path.removeprefix(prefix).removesuffix("/observations")
            valid_from = date.fromisoformat(request.url.params["from"])
            valid_to = date.fromisoformat(request.url.params["to"])
            series_points = []
            for (series_maturity, valid_date), (value, version_id) in sorted(
                observations.items(),
                key=lambda item: item[0][1],
            ):
                if series_maturity != maturity:
                    continue
                if valid_from <= valid_date <= valid_to:
                    series_points.append(
                        v1.SeriesPoint(valid_date=valid_date, value=value, version_id=version_id)
                    )
            series_body = v1.SeriesObservationsResponse(
                data=v1.SeriesObservations(
                    curve_id=CURVE_ID,
                    maturity=maturity,
                    points=series_points,
                ),
                meta=v1.CurveMeta(as_of=CHECKED_AS_OF),
            )
            return httpx.Response(200, json=series_body.model_dump(mode="json"))

        return httpx.Response(404)

    return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", URL)
    monkeypatch.setenv("PROCESSING_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("PROCESSING_DB__PASSWORD", "not-a-secret")


def run(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    *,
    transport: httpx.MockTransport,
    store: RecordingStore | None = None,
    telemetry: Telemetry | None = None,
) -> Run:
    recording = store or RecordingStore()
    exit_code = main(
        argv,
        persistence_transport=transport,
        quality_store=recording,
        telemetry=telemetry,
    )
    captured = capsys.readouterr()
    return Run(exit_code, captured.out, captured.err)


def test_the_scenario_bad_value_is_flagged_and_recorded(capsys: pytest.CaptureFixture[str]) -> None:
    store = RecordingStore()
    transport = _transport(_curve_after_bad_value())

    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=transport,
        store=store,
    )

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    summary = result.summary
    assert summary["event"] == "quality_checked"
    assert summary["warn_count"] == 4
    assert summary["checked_as_of"] == CHECKED_AS_OF.isoformat()
    assert len(store.checks) == 1

    check = store.checks[0]
    ten_y_oct_08 = next(
        value
        for value in check.values
        if value.maturity == "10Y" and value.valid_date == date(2026, 10, 8)
    )
    assert ten_y_oct_08.status is Status.WARN
    oct_08_rules = {
        finding.rule
        for finding in check.findings
        if finding.valid_date == date(2026, 10, 8) and finding.maturity == "10Y"
    }
    assert oct_08_rules == {Rule.RANGE, Rule.JUMP}

    oct_07_missing = {
        finding.maturity
        for finding in check.findings
        if finding.valid_date == date(2026, 10, 7) and finding.rule is Rule.MISSING_MATURITY
    }
    assert oct_07_missing == {"10Y", "30Y"}


def test_an_unknown_curve_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    transport = _transport(_curve_after_bad_value())

    result = run(
        capsys,
        ["unknown-curve", "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=transport,
    )

    assert result.exit_code == 2
    failure = json.loads(result.stderr)
    assert failure["event"] == "quality_check_failed"
    assert failure["error"] == "UnknownCurveError"


def test_from_after_to_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    transport = _transport(_curve_after_bad_value())

    with pytest.raises(SystemExit) as exit_info:
        main(
            [CURVE_ID, "--from", "2026-10-08", "--to", "2026-10-05"],
            persistence_transport=transport,
            quality_store=RecordingStore(),
        )

    assert exit_info.value.code == 2


def test_missing_settings_exit_2(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PROCESSING_PERSISTENCE__URL")

    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=_transport(_curve_after_bad_value()),
    )

    assert result.exit_code == 2
    failure = json.loads(result.stderr)
    assert failure["error"] == "ValidationError"


def test_persistence_unavailable_exits_1_with_a_json_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=httpx.MockTransport(unavailable),
    )

    assert result.exit_code == 1
    failure = json.loads(result.stderr)
    assert failure["event"] == "quality_check_failed"
    assert failure["error"] == "PersistenceReadError"


def points(rec: RecordingMetricExporter, name: str) -> dict[frozenset[tuple[str, str]], float]:
    """Values of one metric in the last export, keyed by label set.

    A counter gives its cumulative sum; a histogram gives its recorded count.
    An empty dict when nothing was exported or the metric has no points.
    """
    if not rec.exported:
        return {}
    values: dict[frozenset[tuple[str, str]], float] = {}
    for resource in rec.exported[-1].resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name != name:
                    continue
                for point in metric.data.data_points:
                    labels = frozenset(
                        (str(k), str(v)) for k, v in (point.attributes or {}).items()
                    )
                    if isinstance(point, HistogramDataPoint):
                        values[labels] = float(point.count)
                    elif isinstance(point, NumberDataPoint):
                        values[labels] = float(point.value)
    return values


def _labels(**labels: str) -> frozenset[tuple[str, str]]:
    return frozenset(labels.items())


def _run_with_metrics(
    capsys: pytest.CaptureFixture[str],
    *,
    observations: dict[tuple[str, date], tuple[float, int]] | None = None,
    transport: httpx.MockTransport | None = None,
    argv: list[str] | None = None,
) -> RecordingMetricExporter:
    telemetry, _, metrics = job_telemetry()
    run(
        capsys,
        argv or [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=transport or _transport(observations or _curve_after_bad_value()),
        telemetry=telemetry,
    )
    return metrics


def test_bad_value_run_counts_one_warn_check(capsys: pytest.CaptureFixture[str]) -> None:
    metrics = _run_with_metrics(capsys)

    assert points(metrics, QUALITY_CHECKS) == {
        _labels(curve=CURVE_ID, status="warn"): 1,
    }


def test_corrected_run_counts_one_passed_check(capsys: pytest.CaptureFixture[str]) -> None:
    metrics = _run_with_metrics(capsys, observations=_curve_after_correction())

    assert points(metrics, QUALITY_CHECKS) == {
        _labels(curve=CURVE_ID, status="passed"): 1,
    }


def test_unreachable_persistence_counts_one_failed_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    metrics = _run_with_metrics(
        capsys,
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"detail": "x"})),
    )

    assert points(metrics, QUALITY_CHECKS)[_labels(curve=CURVE_ID, status="failed")] == 1
    assert points(metrics, CHECK_DURATION)[_labels(curve=CURVE_ID)] == 1


def test_bad_value_run_counts_findings_by_rule(capsys: pytest.CaptureFixture[str]) -> None:
    metrics = _run_with_metrics(capsys)

    findings = points(metrics, QUALITY_FINDINGS)
    warn_by_rule = {
        dict(labels)["rule"]: count
        for labels, count in findings.items()
        if dict(labels)["severity"] == "warn"
    }
    assert warn_by_rule == {"missing-maturity": 2, "range": 1, "jump": 1}


def test_values_checked_counts_the_run_values(capsys: pytest.CaptureFixture[str]) -> None:
    telemetry, _, metrics = job_telemetry()
    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=_transport(_curve_after_bad_value()),
        telemetry=telemetry,
    )

    assert points(metrics, VALUES_CHECKED)[_labels(curve=CURVE_ID)] == result.summary["values"]


def test_duration_is_recorded_on_success(capsys: pytest.CaptureFixture[str]) -> None:
    metrics = _run_with_metrics(capsys)

    assert points(metrics, CHECK_DURATION) == {_labels(curve=CURVE_ID): 1}


def test_unknown_curve_records_no_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    telemetry, _, metrics = job_telemetry()
    run(
        capsys,
        ["unknown-curve", "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=_transport(_curve_after_bad_value()),
        telemetry=telemetry,
    )

    for name in METRIC_NAMES:
        assert points(metrics, name) == {}


def _root_spans(spans: list[ReadableSpan]) -> list[ReadableSpan]:
    return [span for span in spans if span.name == "processing-check-quality"]


def test_a_successful_run_flushes_spans_and_metrics_before_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, spans, metrics = job_telemetry()

    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=_transport(_curve_after_bad_value()),
        telemetry=telemetry,
    )

    assert result.exit_code == 0
    roots = _root_spans(list(spans.get_finished_spans()))
    assert len(roots) == 1
    assert roots[0].parent is None
    assert roots[0].attributes is not None
    assert roots[0].attributes["run_id"] == f"check-quality-{CURVE_ID}-{FROM}-{TO}"
    assert roots[0].attributes["curve_id"] == CURVE_ID
    assert metrics.exported


def test_a_failed_run_flushes_spans_and_metrics_before_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, spans, metrics = job_telemetry()

    result = run(
        capsys,
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"detail": "x"})),
        telemetry=telemetry,
    )

    assert result.exit_code == 1
    roots = _root_spans(list(spans.get_finished_spans()))
    assert len(roots) == 1
    assert roots[0].status.status_code is StatusCode.ERROR
    assert metrics.exported


def test_summary_and_failure_lines_carry_the_root_trace_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()]
    ok_telemetry, ok_spans, _ = job_telemetry()
    failed_telemetry, failed_spans, _ = job_telemetry()

    ok = run(
        capsys,
        arguments,
        transport=_transport(_curve_after_bad_value()),
        telemetry=ok_telemetry,
    )
    failed = run(
        capsys,
        arguments,
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"detail": "x"})),
        telemetry=failed_telemetry,
    )

    (ok_root,) = _root_spans(list(ok_spans.get_finished_spans()))
    (failed_root,) = _root_spans(list(failed_spans.get_finished_spans()))
    assert ok.summary["trace_id"] == format_trace_id(ok_root.context.trace_id)
    assert ok.summary["span_id"] == format_span_id(ok_root.context.span_id)
    failure = json.loads(failed.stderr)
    assert failure["trace_id"] == format_trace_id(failed_root.context.trace_id)
    assert failure["span_id"] == format_span_id(failed_root.context.span_id)


class _FakeConnection:
    call_timeout: int = 0
    client_identifier: str | None = None
    clientinfo: str | None = None


class _FakePool:
    def acquire(self) -> AbstractAsyncContextManager[_FakeConnection]:
        return _acquired()


@asynccontextmanager
async def _acquired() -> AsyncIterator[_FakeConnection]:
    yield _FakeConnection()


def test_the_job_store_traces_its_sessions_with_the_job_tracer() -> None:
    telemetry, spans, _ = job_telemetry()
    settings = DatabaseSettings(dsn="oracle.test:1521/FREEPDB1", password=SecretStr("x"))
    store = oracle_quality_store(
        cast(oracledb.AsyncConnectionPool, _FakePool()), settings, telemetry
    )

    async def probe() -> None:
        assert isinstance(store, OracleQualityStore)
        async with store._session("probe"):
            pass

    asyncio.run(probe())
    telemetry.tracer_provider.force_flush()

    assert [span.name for span in spans.get_finished_spans()] == ["proc_quality.probe"]
