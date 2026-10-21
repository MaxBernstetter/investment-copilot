"""Composition roots of the jobs: the ECB source, ``ING`` and persistence for the load, and
persistence alone for a scenario.

Entry points ``ingestion-load-ecb`` (see ``ingestion.facade.jobs.load_ecb``) and
``ingestion-scenario`` (see ``ingestion.facade.jobs.scenario``). Exit status: ``0`` the
load, replay, scenario or fail-unfinished finished (also with zero rows), ``1`` it failed,
``2`` usage or configuration error.
Every run is one root span; its trace ids go into the JSON summary or failure line, and the
telemetry is flushed before the process exits.
"""

import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Protocol

import httpx
import oracledb
from opentelemetry.metrics import Meter
from opentelemetry.trace import Span, StatusCode
from pydantic import ValidationError

from ingestion.application.load_published_curve import DeliveryStore, LoadPublishedCurve, LoadResult
from ingestion.application.replay_deliveries import (
    ReplayDeliveries,
    ReplayResult,
    StoredDeliveries,
)
from ingestion.application.run_scenario import RunScenario, ScenarioResult
from ingestion.application.track_run import RunLog, TrackRun
from ingestion.config import IngestionSettings
from ingestion.domain.run import Operation
from ingestion.facade.jobs.load_ecb import (
    FailUnfinishedCommand,
    LoadCommand,
    ReplayCommand,
    failure,
    parse_command,
    replay_summary,
    root_span_attributes,
    summary,
    unfinished_summary,
)
from ingestion.facade.jobs.scenario import (
    ScenarioCommand,
    parse_scenario_command,
    scenario_failure,
    scenario_summary,
)
from ingestion.infrastructure.ecb import (
    SOURCE_ID,
    EcbSpotCurveSource,
    InvalidPayloadError,
    parse_delivery,
)
from ingestion.infrastructure.ecb import is_no_data as ecb_is_no_data
from ingestion.infrastructure.http import SourceClient, SourceDisabledError, SourceRequestError
from ingestion.infrastructure.ing import CorruptDeliveryError, OracleDeliveryStore, OracleRunLog
from ingestion.infrastructure.persistence import PersistenceClient, PersistenceWriteError
from ingestion.infrastructure.telemetry import (
    AttemptOnSpan,
    Telemetry,
    setup_telemetry,
    trace_fields,
)

LOAD_ERRORS = (
    SourceDisabledError,
    SourceRequestError,
    InvalidPayloadError,
    CorruptDeliveryError,
    PersistenceWriteError,
    httpx.HTTPError,
    oracledb.Error,
)


SCENARIO_ERRORS = (PersistenceWriteError, httpx.HTTPError)


class Deliveries(DeliveryStore, StoredDeliveries, Protocol):
    """The raw delivery store as the job uses it: loads write it, replay reads it."""


def main(
    argv: Sequence[str] | None = None,
    *,
    source_transport: httpx.AsyncBaseTransport | None = None,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    delivery_store: Deliveries | None = None,
    run_log: RunLog | None = None,
    telemetry: Telemetry | None = None,
) -> int:
    """Run one ECB load or replay. Tests inject the transports, the delivery store and the
    telemetry; the defaults are real (the ``ING`` schema in Oracle, the OTLP exporters only
    when an endpoint is configured)."""
    telemetry = telemetry or setup_telemetry()
    try:
        return _load_ecb(
            argv,
            source_transport,
            persistence_transport,
            delivery_store,
            run_log,
            telemetry,
        )
    finally:
        telemetry.shutdown()


def _load_ecb(
    argv: Sequence[str] | None,
    source_transport: httpx.AsyncBaseTransport | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    delivery_store: Deliveries | None,
    run_log: RunLog | None,
    telemetry: Telemetry,
) -> int:
    try:
        settings = IngestionSettings()
    except ValidationError as error:
        print(failure(None, error, {}), file=sys.stderr)
        return 2
    command = parse_command(
        argv, lookback_business_days=settings.sources.ecb.lookback_business_days
    )
    with telemetry.tracer.start_as_current_span(
        "ingestion-load-ecb", attributes=root_span_attributes(command)
    ) as span:
        trace = trace_fields()
        try:
            if isinstance(command, FailUnfinishedCommand):
                failed_count = asyncio.run(_fail_unfinished(command, settings, run_log))
                print(unfinished_summary(command.run_id, failed_count, trace))
                return 0
            if isinstance(command, ReplayCommand):
                replayed = asyncio.run(
                    _replay(
                        command,
                        settings,
                        persistence_transport,
                        delivery_store,
                        run_log,
                        span,
                    )
                )
                print(replay_summary(replayed, trace))
                return 0
            result = asyncio.run(
                _load(
                    command,
                    settings,
                    source_transport,
                    persistence_transport,
                    delivery_store,
                    run_log,
                    span,
                    telemetry.meter,
                )
            )
        except LOAD_ERRORS as error:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR)
            print(failure(command.run_id, error, trace), file=sys.stderr)
            return 1
        print(summary(result, trace))
    return 0


async def _load(
    command: LoadCommand,
    settings: IngestionSettings,
    source_transport: httpx.AsyncBaseTransport | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    delivery_store: Deliveries | None,
    run_log: RunLog | None,
    span: Span,
    meter: Meter,
) -> LoadResult:
    async with (
        _deliveries(settings, delivery_store) as deliveries,
        _run_log(settings, run_log) as runs,
        SourceClient(
            SOURCE_ID,
            settings.sources.ecb,
            is_no_data=ecb_is_no_data,
            transport=source_transport,
            meter=meter,
        ) as source_client,
        PersistenceClient(settings.persistence, transport=persistence_transport) as store,
    ):
        load = LoadPublishedCurve(EcbSpotCurveSource(source_client), deliveries, store)
        tracked = await TrackRun(AttemptOnSpan(runs, span))(
            command.run_id, command.operation, load(command.windows, command.run_id)
        )
        return LoadResult(command.run_id, tracked.attempt, tracked.steps)


async def _fail_unfinished(
    command: FailUnfinishedCommand, settings: IngestionSettings, run_log: RunLog | None
) -> int:
    """Only the run log is opened: no source, no persistence, no delivery store."""
    async with _run_log(settings, run_log) as runs:
        return await runs.fail_unfinished(command.run_id, command.error_type, command.error_message)


async def _replay(
    command: ReplayCommand,
    settings: IngestionSettings,
    persistence_transport: httpx.AsyncBaseTransport | None,
    delivery_store: Deliveries | None,
    run_log: RunLog | None,
    span: Span,
) -> ReplayResult:
    """No source client is created: replay reads stored payloads only."""
    async with (
        _deliveries(settings, delivery_store) as deliveries,
        _run_log(settings, run_log) as runs,
        PersistenceClient(settings.persistence, transport=persistence_transport) as store,
    ):
        replay = ReplayDeliveries(SOURCE_ID, parse_delivery, deliveries, store)
        tracked = await TrackRun(AttemptOnSpan(runs, span))(
            command.run_id,
            Operation.REPLAY,
            replay(command.fetched_from, command.fetched_to, command.run_id),
        )
        return ReplayResult(command.run_id, tracked.attempt, tracked.steps)


def run_scenario(
    argv: Sequence[str] | None = None,
    *,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    telemetry: Telemetry | None = None,
) -> int:
    """Run one scenario against its simulated curve. Tests inject the transport, the pause
    and the telemetry; the defaults are real (persistence over HTTP, real seconds)."""
    telemetry = telemetry or setup_telemetry()
    try:
        return _run_scenario(argv, persistence_transport, sleep, telemetry)
    finally:
        telemetry.shutdown()


def _run_scenario(
    argv: Sequence[str] | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    sleep: Callable[[float], Awaitable[None]],
    telemetry: Telemetry,
) -> int:
    try:
        settings = IngestionSettings()
    except ValidationError as error:
        print(scenario_failure(None, error, {}), file=sys.stderr)
        return 2
    command = parse_scenario_command(argv)
    with telemetry.tracer.start_as_current_span(
        "ingestion-scenario", attributes={"scenario": command.scenario.name}
    ) as span:
        trace = trace_fields()
        try:
            result = asyncio.run(_scenario(command, settings, persistence_transport, sleep))
        except SCENARIO_ERRORS as error:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR)
            print(scenario_failure(command.scenario.name, error, trace), file=sys.stderr)
            return 1
        print(scenario_summary(result, trace))
    return 0


async def _scenario(
    command: ScenarioCommand,
    settings: IngestionSettings,
    persistence_transport: httpx.AsyncBaseTransport | None,
    sleep: Callable[[float], Awaitable[None]],
) -> ScenarioResult:
    """No source client and no delivery store: a scenario writes through persistence only."""
    async with PersistenceClient(settings.persistence, transport=persistence_transport) as store:
        scenario = RunScenario(store, sleep)
        return await scenario(command.scenario, command.event_names)


@asynccontextmanager
async def _deliveries(
    settings: IngestionSettings, injected: Deliveries | None
) -> AsyncIterator[Deliveries]:
    if injected is not None:
        yield injected
        return
    async with OracleDeliveryStore(settings.db) as store:
        yield store


@asynccontextmanager
async def _run_log(settings: IngestionSettings, injected: RunLog | None) -> AsyncIterator[RunLog]:
    if injected is not None:
        yield injected
        return
    async with OracleRunLog(settings.db) as runs:
        yield runs
