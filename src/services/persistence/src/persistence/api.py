"""Composition root of the ``api`` process: wires Oracle into the REST facade.

Run with: ``uvicorn --factory persistence.api:create_app_from_environment``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from persistence.application.get_curve_as_of import GetCurveAsOf
from persistence.application.get_series_as_of import GetSeriesAsOf
from persistence.application.get_value_versions import GetValueVersions
from persistence.application.record_versions import RecordVersions
from persistence.config import Settings
from persistence.facade.rest.app import Services, create_app
from persistence.infrastructure.oracle import OracleObservationRepository, create_pool


def create_app_from_environment() -> FastAPI:
    return create_app(partial(oracle_services, Settings()))


@asynccontextmanager
async def oracle_services(settings: Settings) -> AsyncIterator[Services]:
    pool = create_pool(
        dsn=settings.db_dsn,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        acquire_timeout_ms=settings.db_acquire_timeout_ms,
    )
    try:
        repository = OracleObservationRepository(pool, call_timeout_ms=settings.db_call_timeout_ms)
        yield Services(
            RecordVersions(repository),
            repository.is_reachable,
            GetCurveAsOf(repository),
            GetSeriesAsOf(repository),
            GetValueVersions(repository),
        )
    finally:
        await pool.close()
