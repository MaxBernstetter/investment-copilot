"""Composition root of the ``job`` process: wires the ECB source, persistence and the spool.

Entry point ``ingestion-load-ecb`` (see ``ingestion.facade.jobs.load_ecb``). Exit
status: ``0`` the load finished (also with zero rows); ``1`` the load failed, or
persistence refused spooled data (set aside in the spool); ``2`` usage or configuration
error; ``3`` deferred: persistence was unavailable and fetched data waits in the spool.
"""

import asyncio
import sys
from collections.abc import Sequence

import httpx
from obstore.exceptions import BaseError as SpoolStoreError
from pydantic import ValidationError

from ingestion.application.load_published_curve import LoadPublishedCurve, LoadResult
from ingestion.application.spool import DeliverySpool
from ingestion.config import IngestionSettings
from ingestion.facade.jobs.load_ecb import LoadCommand, failure, parse_command, summary
from ingestion.infrastructure.ecb import SOURCE_ID, EcbSpotCurveSource, InvalidPayloadError
from ingestion.infrastructure.ecb import is_no_data as ecb_is_no_data
from ingestion.infrastructure.http import SourceClient, SourceDisabledError, SourceRequestError
from ingestion.infrastructure.persistence import PersistenceClient, PersistenceWriteError
from ingestion.infrastructure.spool import open_spool

DEFERRED = 3

LOAD_ERRORS = (
    SourceDisabledError,
    SourceRequestError,
    InvalidPayloadError,
    PersistenceWriteError,
    SpoolStoreError,
    httpx.HTTPError,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    source_transport: httpx.AsyncBaseTransport | None = None,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    spool: DeliverySpool | None = None,
) -> int:
    """Run one ECB load. Transports and spool are injected by tests; the defaults are real."""
    try:
        settings = IngestionSettings()
    except ValidationError as error:
        print(failure(None, error), file=sys.stderr)
        return 2
    command = parse_command(
        argv, lookback_business_days=settings.sources.ecb.lookback_business_days
    )
    try:
        result = asyncio.run(
            _load(
                command,
                settings,
                source_transport,
                persistence_transport,
                spool or open_spool(settings.spool, SOURCE_ID),
            )
        )
    except LOAD_ERRORS as error:
        print(failure(command.run_id, error), file=sys.stderr)
        return 1
    print(summary(result))
    if result.is_deferred:
        return DEFERRED
    return 1 if result.drain.rejected else 0


async def _load(
    command: LoadCommand,
    settings: IngestionSettings,
    source_transport: httpx.AsyncBaseTransport | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    spool: DeliverySpool,
) -> LoadResult:
    async with (
        SourceClient(
            SOURCE_ID, settings.sources.ecb, is_no_data=ecb_is_no_data, transport=source_transport
        ) as source_client,
        PersistenceClient(settings.persistence, transport=persistence_transport) as store,
    ):
        load = LoadPublishedCurve(EcbSpotCurveSource(source_client), store, spool)
        return await load(command.windows, command.run_id)
