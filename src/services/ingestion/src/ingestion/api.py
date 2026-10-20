"""Composition root of the ``api`` process: wires the ING database into the REST facade.

Run with: ``uvicorn --factory ingestion.api:create_app_from_environment``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from ingestion.config import ApiSettings, DatabaseSettings
from ingestion.facade.rest.app import Services, create_app
from ingestion.infrastructure.ing.pool import OracleHealth, create_pool


def create_app_from_environment() -> FastAPI:
    return create_app(partial(ing_services, ApiSettings().db))


@asynccontextmanager
async def ing_services(settings: DatabaseSettings) -> AsyncIterator[Services]:
    pool = create_pool(settings)
    try:
        yield Services(OracleHealth(pool, call_timeout_ms=settings.call_timeout_ms).is_reachable)
    finally:
        await pool.close()
