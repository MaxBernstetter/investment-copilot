"""Composition root of the ``processing-check-quality`` job.

Entry point ``processing-check-quality`` (see ``processing.facade.jobs.check_quality``).
Exit status: ``0`` the check finished (also when nothing was known), ``1`` persistence or
Oracle failed, ``2`` usage or configuration error (including an unknown curve).
"""

import asyncio
import sys
from collections.abc import Sequence

import httpx
import oracledb
from pydantic import ValidationError

from processing.application.check_quality import CheckQuality, CheckSummary, UnknownCurveError
from processing.application.ports import QualityStore
from processing.config import JobSettings
from processing.facade.jobs.check_quality import CheckCommand, failure, parse_command, summary
from processing.infrastructure.persistence import PersistenceClient, PersistenceReadError
from processing.infrastructure.proc import OracleQualityStore, create_pool

JOB_ERRORS = (PersistenceReadError, httpx.HTTPError, oracledb.Error)


def main(
    argv: Sequence[str] | None = None,
    *,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    quality_store: QualityStore | None = None,
) -> int:
    """Run one quality check. Tests inject the persistence transport and the store."""
    try:
        settings = JobSettings()
    except ValidationError as error:
        print(failure(None, error), file=sys.stderr)
        return 2
    command = parse_command(argv)
    try:
        result = asyncio.run(
            _check(command, settings, persistence_transport, quality_store),
        )
    except UnknownCurveError as error:
        print(failure(command.run_id, error), file=sys.stderr)
        return 2
    except JOB_ERRORS as error:
        print(failure(command.run_id, error), file=sys.stderr)
        return 1
    print(summary(result))
    return 0


async def _check(
    command: CheckCommand,
    settings: JobSettings,
    persistence_transport: httpx.AsyncBaseTransport | None,
    quality_store: QualityStore | None,
) -> CheckSummary:
    persistence = settings.persistence
    async with PersistenceClient(
        str(persistence.url),
        persistence.timeout_seconds,
        transport=persistence_transport,
    ) as reader:
        if quality_store is not None:
            use_case = CheckQuality(reader, quality_store)
            return await use_case(
                command.curve_id,
                command.valid_from,
                command.valid_to,
                command.run_id,
            )

        db = settings.db.model_copy(update={"pool_min": 1, "pool_max": 1})
        pool = create_pool(db)
        try:
            store = OracleQualityStore(pool, call_timeout_ms=db.call_timeout_ms)
            use_case = CheckQuality(reader, store)
            return await use_case(
                command.curve_id,
                command.valid_from,
                command.valid_to,
                command.run_id,
            )
        finally:
            await pool.close()
