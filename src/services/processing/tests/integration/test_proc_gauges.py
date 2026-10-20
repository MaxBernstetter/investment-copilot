import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricsData

from processing.application.alerts import LatestCheckRun
from processing.domain.assessment import DayStatus, QualityCheck, ValueStatus
from processing.domain.quality import Status
from processing.infrastructure.proc import OracleQualityStore
from processing.infrastructure.proc_gauges import ALERT_ACTIVE, LAST_SUCCESS, register_proc_gauges
from tests.integration.conftest import OracleDatabase
from tests.integration.test_quality_store import (
    VALID_FROM,
    VALID_TO,
    _with_store,
    record,
    sample_check,
)

CURVE = "it-gauge-curve"
T1 = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
T2 = T1 + timedelta(hours=1)


@pytest.fixture(autouse=True)
def remove_gauge_curve_rows(oracle: OracleDatabase) -> Iterator[None]:
    """The database is shared by the module; the other modules count its rows."""
    yield
    with oracle.connect_as_owner() as connection:
        cursor = connection.cursor()
        cursor.execute("delete from quality_finding where curve_id = :c", [CURVE])
        cursor.execute("delete from value_quality where curve_id = :c", [CURVE])
        cursor.execute("delete from checked_day where curve_id = :c", [CURVE])
        cursor.execute("delete from check_run where curve_id = :c", [CURVE])
        connection.commit()


def check(*, as_of: datetime, warn: bool) -> QualityCheck:
    base = sample_check(checked_as_of=as_of)
    if warn:
        return replace(base, curve_id=CURVE)
    return replace(
        base,
        curve_id=CURVE,
        days=(
            DayStatus(VALID_FROM, Status.PASSED),
            DayStatus(VALID_TO, Status.PASSED),
        ),
        values=(
            ValueStatus(1, "10Y", VALID_FROM, Status.PASSED),
            ValueStatus(2, "10Y", VALID_TO, Status.PASSED),
        ),
        findings=(),
    )


def collect_gauges(oracle: OracleDatabase) -> MetricsData | None:
    async def action(store: OracleQualityStore) -> MetricsData | None:
        reader = InMemoryMetricReader()
        meter = MeterProvider(metric_readers=[reader]).get_meter("integration")
        register_proc_gauges(meter, store.latest_check_runs, asyncio.get_running_loop())
        return await asyncio.to_thread(reader.get_metrics_data)

    return asyncio.run(_with_store(oracle, action))


def gauge_value(data: MetricsData | None, name: str, attributes: dict[str, str]) -> float:
    assert data is not None
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name != name:
                    continue
                for point in metric.data.data_points:
                    if dict(point.attributes or {}) == attributes:
                        return float(point.value)  # type: ignore[union-attr]
    raise AssertionError(f"no point {name} {attributes}")


def test_quality_warn_fires_then_clears(oracle: OracleDatabase) -> None:
    record(oracle, check(as_of=T1, warn=True))
    alert = {"alert": "quality-warn", "curve": CURVE}
    assert gauge_value(collect_gauges(oracle), ALERT_ACTIVE, alert) == 1

    record(oracle, check(as_of=T2, warn=False))
    assert gauge_value(collect_gauges(oracle), ALERT_ACTIVE, alert) == 0


def test_freshness_is_the_latest_recorded_at(oracle: OracleDatabase) -> None:
    record(oracle, check(as_of=T1 + timedelta(days=1), warn=True))

    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select max(recorded_at) from proc.check_run where curve_id = :c", [CURVE])
        latest = cursor.fetchone()[0]

    expected = latest.replace(tzinfo=UTC).timestamp()
    value = gauge_value(collect_gauges(oracle), LAST_SUCCESS, {"curve": CURVE})
    assert value == pytest.approx(expected, abs=1e-3)


def test_latest_check_runs_is_one_row_per_curve(oracle: OracleDatabase) -> None:
    as_of = T1 + timedelta(days=2)
    record(oracle, check(as_of=as_of, warn=True))
    record(oracle, check(as_of=as_of + timedelta(hours=1), warn=False))

    async def read(store: OracleQualityStore) -> list[LatestCheckRun]:
        return await store.latest_check_runs()

    runs = asyncio.run(_with_store(oracle, read))

    curve_ids = [run.curve_id for run in runs]
    assert len(curve_ids) == len(set(curve_ids))
    ours = [run for run in runs if run.curve_id == CURVE]
    assert len(ours) == 1
    assert ours[0].warn_days == 0
