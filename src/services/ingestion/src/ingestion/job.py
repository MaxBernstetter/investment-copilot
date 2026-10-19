"""Composition roots of the jobs: the ECB source, ``ING`` and persistence for the load, and
persistence alone for a scenario.

Entry points ``ingestion-load-ecb`` (see ``ingestion.facade.jobs.load_ecb``) and
``ingestion-scenario`` (see ``ingestion.facade.jobs.scenario``). Exit status: ``0`` the
load, replay or scenario finished (also with zero rows), ``1`` it failed, ``2`` usage or
configuration error.
"""

import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Protocol

import httpx
import oracledb
from pydantic import ValidationError

from ingestion.application.load_published_curve import DeliveryStore, LoadPublishedCurve, LoadResult
from ingestion.application.replay_deliveries import (
    ReplayDeliveries,
    ReplayResult,
    StoredDeliveries,
)
from ingestion.application.run_scenario import RunScenario, ScenarioResult
from ingestion.config import IngestionSettings
from ingestion.facade.jobs.load_ecb import (
    LoadCommand,
    ReplayCommand,
    failure,
    parse_command,
    replay_summary,
    summary,
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
from ingestion.infrastructure.ing import CorruptDeliveryError, OracleDeliveryStore
from ingestion.infrastructure.persistence import PersistenceClient, PersistenceWriteError

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
) -> int:
    """Run one ECB load or replay. Tests inject the transports and the delivery store; the
    defaults are real (the ``ING`` schema in Oracle)."""
    try:
        settings = IngestionSettings()
    except ValidationError as error:
        print(failure(None, error), file=sys.stderr)
        return 2
    command = parse_command(
        argv, lookback_business_days=settings.sources.ecb.lookback_business_days
    )
    try:
        if isinstance(command, ReplayCommand):
            replayed = asyncio.run(
                _replay(command, settings, persistence_transport, delivery_store)
            )
            print(replay_summary(replayed))
            return 0
        result = asyncio.run(
            _load(command, settings, source_transport, persistence_transport, delivery_store)
        )
    except LOAD_ERRORS as error:
        print(failure(command.run_id, error), file=sys.stderr)
        return 1
    print(summary(result))
    return 0


async def _load(
    command: LoadCommand,
    settings: IngestionSettings,
    source_transport: httpx.AsyncBaseTransport | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    delivery_store: Deliveries | None,
) -> LoadResult:
    async with (
        _deliveries(settings, delivery_store) as deliveries,
        SourceClient(
            SOURCE_ID, settings.sources.ecb, is_no_data=ecb_is_no_data, transport=source_transport
        ) as source_client,
        PersistenceClient(settings.persistence, transport=persistence_transport) as store,
    ):
        load = LoadPublishedCurve(EcbSpotCurveSource(source_client), deliveries, store)
        return await load(command.windows, command.run_id)


async def _replay(
    command: ReplayCommand,
    settings: IngestionSettings,
    persistence_transport: httpx.AsyncBaseTransport | None,
    delivery_store: Deliveries | None,
) -> ReplayResult:
    """No source client is created: replay reads stored payloads only."""
    async with (
        _deliveries(settings, delivery_store) as deliveries,
        PersistenceClient(settings.persistence, transport=persistence_transport) as store,
    ):
        replay = ReplayDeliveries(SOURCE_ID, parse_delivery, deliveries, store)
        return await replay(command.fetched_from, command.fetched_to, command.run_id)


def run_scenario(
    argv: Sequence[str] | None = None,
    *,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """Run one scenario against its simulated curve. Tests inject the transport and the
    pause; the defaults are real (persistence over HTTP, real seconds)."""
    try:
        settings = IngestionSettings()
    except ValidationError as error:
        print(scenario_failure(None, error), file=sys.stderr)
        return 2
    command = parse_scenario_command(argv)
    try:
        result = asyncio.run(_scenario(command, settings, persistence_transport, sleep))
    except SCENARIO_ERRORS as error:
        print(scenario_failure(command.scenario.name, error), file=sys.stderr)
        return 1
    print(scenario_summary(result))
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
