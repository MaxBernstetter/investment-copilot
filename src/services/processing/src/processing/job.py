"""Composition root of the ``processing-check-quality`` job.

Entry point ``processing-check-quality`` (see ``processing.facade.jobs.check_quality``).
Exit status: ``0`` the check finished (also when nothing was known), ``1`` persistence or
Oracle failed, ``2`` usage or configuration error (including an unknown curve).
Every run is one root span; its trace ids go into the JSON summary or failure line, and the
telemetry is flushed before the process exits.
"""

import asyncio
import sys
from collections.abc import Sequence

import httpx
import oracledb
from opentelemetry.trace import StatusCode
from pydantic import ValidationError

from processing.application.check_quality import CheckQuality, CheckSummary, UnknownCurveError
from processing.application.ports import QualityStore
from processing.config import JobSettings
from processing.facade.jobs.check_quality import CheckCommand, failure, parse_command, summary
from processing.infrastructure.persistence import PersistenceClient, PersistenceReadError
from processing.infrastructure.proc import OracleQualityStore, create_pool
from processing.infrastructure.telemetry import Telemetry, setup_telemetry, trace_fields

JOB_ERRORS = (PersistenceReadError, httpx.HTTPError, oracledb.Error)


def main(
    argv: Sequence[str] | None = None,
    *,
    persistence_transport: httpx.AsyncBaseTransport | None = None,
    quality_store: QualityStore | None = None,
    telemetry: Telemetry | None = None,
) -> int:
    """Run one quality check. Tests inject the persistence transport, the store and telemetry."""
    telemetry = telemetry or setup_telemetry()
    try:
        return _run(argv, persistence_transport, quality_store, telemetry)
    finally:
        telemetry.shutdown()


def _run(
    argv: Sequence[str] | None,
    persistence_transport: httpx.AsyncBaseTransport | None,
    quality_store: QualityStore | None,
    telemetry: Telemetry,
) -> int:
    try:
        settings = JobSettings()
    except ValidationError as error:
        print(failure(None, error, {}), file=sys.stderr)
        return 2
    command = parse_command(argv)
    with telemetry.tracer.start_as_current_span(
        "processing-check-quality",
        attributes={"run_id": command.run_id, "curve_id": command.curve_id},
    ) as span:
        trace = trace_fields()
        try:
            result = asyncio.run(
                _check(command, settings, persistence_transport, quality_store, telemetry),
            )
        except UnknownCurveError as error:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR)
            print(failure(command.run_id, error, trace), file=sys.stderr)
            return 2
        except JOB_ERRORS as error:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR)
            print(failure(command.run_id, error, trace), file=sys.stderr)
            return 1
        print(summary(result, trace))
    return 0


async def _check(
    command: CheckCommand,
    settings: JobSettings,
    persistence_transport: httpx.AsyncBaseTransport | None,
    quality_store: QualityStore | None,
    telemetry: Telemetry,
) -> CheckSummary:
    persistence = settings.persistence
    async with PersistenceClient(
        str(persistence.url),
        persistence.timeout_seconds,
        transport=persistence_transport,
        telemetry=telemetry,
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
            store = OracleQualityStore(
                pool,
                call_timeout_ms=db.call_timeout_ms,
                tracer=telemetry.tracer,
            )
            use_case = CheckQuality(reader, store)
            return await use_case(
                command.curve_id,
                command.valid_from,
                command.valid_to,
                command.run_id,
            )
        finally:
            await pool.close()
