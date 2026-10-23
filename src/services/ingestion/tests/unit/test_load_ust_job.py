"""The US Treasury load job end to end inside ingestion: recorded Treasury CSVs in, contract
requests to a persistence stub out. No live source and no network are used."""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
import pytest
from opentelemetry.sdk.metrics._internal.point import NumberDataPoint

from ingestion.infrastructure.telemetry import Telemetry
from ingestion.job import load_ust
from tests.fake_deliveries import FakeDeliveryStore
from tests.fake_run_log import FakeRunLog
from tests.fake_telemetry import RecordingMetricExporter, job_telemetry
from tests.recorded import (
    UST_EMPTY_2027,
    UST_NEW_COLUMN_2025,
    UST_YEAR_1990,
    UST_YEAR_2004,
    UST_YEAR_2025,
    ust_response,
)
from tests.stub_persistence import URL, StubPersistence

UST_DATA_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)
SCHEMA_COUNTER = "ingestion_compatible_schema_changes_total"


@dataclass
class StubUst:
    """Answers the request for each year with the named recording of that year."""

    files: dict[int, str]
    """Year to recording; a year not listed answers with the empty 2027 body (no data)."""
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        year = int(request.url.path.split("/")[-2])
        return ust_response(self.files.get(year, UST_EMPTY_2027))

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


@dataclass
class Run:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.stdout)
        return result


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", URL)
    monkeypatch.setenv("INGESTION_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "not-a-secret")
    # Pacing is the source client's concern (tested there); here it would only slow tests.
    monkeypatch.setenv("INGESTION_SOURCES__UST__MIN_INTERVAL_SECONDS", "0")


def run(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    ust: StubUst,
    persistence: StubPersistence,
    deliveries: FakeDeliveryStore | None = None,
    run_log: FakeRunLog | None = None,
    telemetry: Telemetry | None = None,
) -> Run:
    exit_code = load_ust(
        argv,
        source_transport=ust.transport,
        persistence_transport=persistence.transport,
        delivery_store=deliveries or FakeDeliveryStore(),
        run_log=run_log or FakeRunLog(),
        telemetry=telemetry,
    )
    captured = capsys.readouterr()
    return Run(exit_code, captured.out, captured.err)


def test_daily_load_requests_the_year_of_the_valid_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ust = StubUst({2025: UST_YEAR_2025})

    run(capsys, ["daily", "--valid-date", "2025-12-31"], ust, StubPersistence())

    [request] = ust.requests
    assert str(request.url) == UST_DATA_URL.format(year=2025)


def test_daily_load_stores_the_par_curve_on_grid_2_with_the_short_tenors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ust = StubUst({2025: UST_YEAR_2025})
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2025-12-31"], ust, persistence)

    assert result.exit_code == 0
    stored = persistence.observations
    assert {(o.curve_id, o.source_id) for o in stored} == {("ust-par", "ust")}
    assert {o.maturity for o in stored if o.valid_date == date(2025, 2, 18)} >= {"1.5M", "30Y"}
    assert result.summary["recorded_count"] == len(stored)
    assert result.summary["delivered_count"] == len(stored)


def test_the_run_id_and_the_span_carry_the_ust_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, spans, _ = job_telemetry()
    ust = StubUst({2025: UST_YEAR_2025})

    result = run(
        capsys, ["daily", "--valid-date", "2025-12-31"], ust, StubPersistence(), telemetry=telemetry
    )

    assert result.exit_code == 0
    [span] = spans.get_finished_spans()
    assert span.name == "ingestion-load-ust"
    assert dict(span.attributes or {})["run_id"] == "ust-daily-2025-12-31"
    assert dict(span.attributes or {})["source"] == "ust"


def test_history_requests_one_file_per_calendar_year_in_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ust = StubUst({1990: UST_YEAR_1990, 2004: UST_YEAR_2004})
    persistence = StubPersistence()

    result = run(
        capsys, ["history", "--start", "1990-01-01", "--end", "2004-12-31"], ust, persistence
    )

    assert result.exit_code == 0
    assert [str(r.url) for r in ust.requests] == [
        UST_DATA_URL.format(year=year) for year in range(1990, 2005)
    ]
    assert {o.run_id for o in persistence.observations} == {"ust-history-1990-01-01-2004-12-31"}
    ninety = {o.maturity for o in persistence.observations if o.valid_date.year == 1990}
    assert ninety == {"3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"}


def test_an_unknown_column_is_loaded_and_counted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, _, metrics = job_telemetry()
    ust = StubUst({2025: UST_NEW_COLUMN_2025})
    persistence = StubPersistence()

    result = run(
        capsys,
        ["daily", "--valid-date", "2025-12-31"],
        ust,
        persistence,
        telemetry=telemetry,
    )

    assert result.exit_code == 0
    assert persistence.observations
    assert _counter_total(metrics, SCHEMA_COUNTER) == 1


def _counter_total(metrics: RecordingMetricExporter, name: str) -> float:
    total = 0.0
    for batch in metrics.exported:
        for resource in batch.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    if metric.name == name:
                        total += sum(
                            point.value
                            for point in metric.data.data_points
                            if isinstance(point, NumberDataPoint)
                        )
    return total
