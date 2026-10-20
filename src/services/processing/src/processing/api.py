"""Composition root of the ``api`` process: wires the processing database into the REST facade.

Run with: ``uvicorn --factory processing.api:create_app_from_environment``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.config import ApiSettings, DatabaseSettings
from processing.facade.rest.app import Services, create_app
from processing.infrastructure.proc import OracleHealth, OracleQualityStore, create_pool
from processing.infrastructure.telemetry import Telemetry, setup_telemetry


def create_app_from_environment() -> FastAPI:
    telemetry = setup_telemetry()
    app = create_app(partial(proc_services, ApiSettings().db, telemetry))
    instrument_app(app, telemetry)
    return app


def instrument_app(app: FastAPI, telemetry: Telemetry) -> None:
    """Trace the requests of the app and record their metrics with the given providers."""
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=telemetry.tracer_provider,
        meter_provider=telemetry.meter_provider,
    )


@asynccontextmanager
async def proc_services(
    settings: DatabaseSettings, telemetry: Telemetry
) -> AsyncIterator[Services]:
    pool = create_pool(settings)
    store = OracleQualityStore(
        pool, call_timeout_ms=settings.call_timeout_ms, tracer=telemetry.tracer
    )
    try:
        yield Services(
            OracleHealth(pool, call_timeout_ms=settings.call_timeout_ms).is_reachable,
            GetQualityDays(store),
            GetValueQuality(store),
        )
    finally:
        await pool.close()
        telemetry.shutdown()
