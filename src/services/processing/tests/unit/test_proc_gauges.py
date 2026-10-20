import asyncio
import io
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import oracledb
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    InMemoryMetricReader,
    MetricsData,
    PeriodicExportingMetricReader,
)

from processing.application.alerts import LatestCheckRun
from processing.infrastructure.proc_gauges import ALERT_ACTIVE, LAST_SUCCESS, register_proc_gauges

RUNS = [
    LatestCheckRun("ecb-aaa-spot-sim", datetime(2026, 10, 9, 8, 0, tzinfo=UTC), 2),
    LatestCheckRun("ecb-bbb-spot-sim", datetime(2026, 10, 8, 7, 30, tzinfo=UTC), 0),
]
Read = Callable[[], Awaitable[list[LatestCheckRun]]]


def points(data: MetricsData | None, name: str) -> dict[tuple[tuple[str, str], ...], float]:
    """The data points of one gauge keyed by their sorted attributes; none when nothing was read."""
    result: dict[tuple[tuple[str, str], ...], float] = {}
    if data is None:
        return result
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name != name:
                    continue
                for point in metric.data.data_points:
                    key = tuple(
                        sorted((str(k), str(v)) for k, v in (point.attributes or {}).items())
                    )
                    result[key] = float(point.value)  # type: ignore[union-attr]
    return result


def collect_on_a_thread(read: Read) -> MetricsData | None:
    """Register the gauges on a running loop, then collect from a worker thread as a scrape does."""
    reader = InMemoryMetricReader()

    async def scenario() -> MetricsData | None:
        meter = MeterProvider(metric_readers=[reader]).get_meter("test")
        register_proc_gauges(meter, read, asyncio.get_running_loop())
        return await asyncio.to_thread(reader.get_metrics_data)

    return asyncio.run(scenario())


def test_gauges_report_alert_and_freshness_per_curve() -> None:
    async def read() -> list[LatestCheckRun]:
        return RUNS

    data = collect_on_a_thread(read)

    assert points(data, ALERT_ACTIVE) == {
        (("alert", "quality-warn"), ("curve", "ecb-aaa-spot-sim")): 1,
        (("alert", "quality-warn"), ("curve", "ecb-bbb-spot-sim")): 0,
    }
    assert points(data, LAST_SUCCESS) == {
        (("curve", "ecb-aaa-spot-sim"),): datetime(2026, 10, 9, 8, 0, tzinfo=UTC).timestamp(),
        (("curve", "ecb-bbb-spot-sim"),): datetime(2026, 10, 8, 7, 30, tzinfo=UTC).timestamp(),
    }


def test_a_failing_read_reports_no_points() -> None:
    async def read() -> list[LatestCheckRun]:
        raise oracledb.DatabaseError("ORA-03114: not connected to Oracle")

    data = collect_on_a_thread(read)

    assert points(data, ALERT_ACTIVE) == {}
    assert points(data, LAST_SUCCESS) == {}


def test_collection_on_the_loop_thread_reports_no_points() -> None:
    async def read() -> list[LatestCheckRun]:
        raise AssertionError("the read must not run on the loop thread")

    reader = InMemoryMetricReader()

    async def scenario() -> MetricsData | None:
        meter = MeterProvider(metric_readers=[reader]).get_meter("test")
        register_proc_gauges(meter, read, asyncio.get_running_loop())
        # Collected on the loop thread itself, as during shutdown.
        return reader.get_metrics_data()

    data = asyncio.run(scenario())

    assert points(data, ALERT_ACTIVE) == {}
    assert points(data, LAST_SUCCESS) == {}


def test_a_closed_loop_reports_no_points(caplog: pytest.LogCaptureFixture) -> None:
    async def read() -> list[LatestCheckRun]:
        return RUNS

    loop = asyncio.new_event_loop()
    reader = InMemoryMetricReader()
    register_proc_gauges(MeterProvider(metric_readers=[reader]).get_meter("test"), read, loop)
    loop.close()

    data = reader.get_metrics_data()

    assert points(data, ALERT_ACTIVE) == {}
    assert points(data, LAST_SUCCESS) == {}
    assert "event loop is closed" in caplog.text


def test_shutdown_off_the_loop_does_not_wait_for_the_loop() -> None:
    async def read() -> list[LatestCheckRun]:
        return RUNS

    async def scenario() -> float:
        reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(out=io.StringIO()), export_interval_millis=60_000
        )
        provider = MeterProvider(metric_readers=[reader])
        register_proc_gauges(provider.get_meter("test"), read, asyncio.get_running_loop())
        started = time.monotonic()
        await asyncio.to_thread(provider.shutdown)
        return time.monotonic() - started

    assert asyncio.run(scenario()) < 1.0
