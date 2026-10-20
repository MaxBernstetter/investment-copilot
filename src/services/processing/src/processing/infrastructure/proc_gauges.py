"""Gauges of the business state that PROC stores: the quality-warn alert and the quality freshness.

The gauges are observable: the ``api`` process evaluates them at collection time, so the values
come from the database on each scrape. The collection runs on the reader thread of the metric
reader while the database pool lives on the event loop, so each callback hops to the loop. A
collection on the loop thread would wait on itself, so it reports no points. The ``api`` shuts
its telemetry down off the loop, so the final collection runs on the exporter thread. A failed or
timed-out read, or a closed loop, also reports no points.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

import oracledb
from opentelemetry.metrics import CallbackOptions, Meter, Observation

from processing.application.alerts import QUALITY_WARN, LatestCheckRun, quality_warn_active

ALERT_ACTIVE = "yl_processing_alert_active"
LAST_SUCCESS = "yl_processing_quality_last_success_timestamp_seconds"
GAUGE_NAMES = (ALERT_ACTIVE, LAST_SUCCESS)

_logger = logging.getLogger(__name__)


def register_proc_gauges(
    meter: Meter,
    read: Callable[[], Awaitable[list[LatestCheckRun]]],
    loop: asyncio.AbstractEventLoop,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    """Register the alert and freshness gauges; ``read`` runs on ``loop`` at each collection."""

    def latest_runs() -> list[LatestCheckRun]:
        if _on_loop_thread(loop):
            return []
        coroutine = _await(read)
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except RuntimeError:
            coroutine.close()
            _logger.warning("quality gauges not collected: the event loop is closed")
            return []
        try:
            return future.result(timeout=timeout_seconds)
        except (oracledb.Error, TimeoutError):
            future.cancel()
            _logger.warning("quality gauges not collected: the PROC read failed or timed out")
            return []

    def alert_observations(_options: CallbackOptions) -> Iterable[Observation]:
        return [
            Observation(
                1 if quality_warn_active(run) else 0,
                {"alert": QUALITY_WARN, "curve": run.curve_id},
            )
            for run in latest_runs()
        ]

    def freshness_observations(_options: CallbackOptions) -> Iterable[Observation]:
        return [
            Observation(run.recorded_at.timestamp(), {"curve": run.curve_id})
            for run in latest_runs()
        ]

    meter.create_observable_gauge(
        ALERT_ACTIVE,
        callbacks=[alert_observations],
        unit="",
        description="1 while the business alert is active for the curve",
    )
    meter.create_observable_gauge(
        LAST_SUCCESS,
        callbacks=[freshness_observations],
        unit="s",
        description="When the latest quality check run of the curve was recorded (UTC epoch)",
    )


async def _await(read: Callable[[], Awaitable[list[LatestCheckRun]]]) -> list[LatestCheckRun]:
    return await read()


def _on_loop_thread(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False
