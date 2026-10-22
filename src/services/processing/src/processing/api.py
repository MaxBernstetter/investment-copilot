"""Composition root of the ``api`` process: wires the processing database into the REST facade.

Run with: ``uvicorn --factory processing.api:create_app_from_environment``
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from processing.application.get_measures import GetMeasures
from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.config import ApiSettings
from processing.facade.rest.app import Services, create_app
from processing.infrastructure.persistence import PersistenceClient
from processing.infrastructure.proc import OracleHealth, OracleQualityStore, create_pool
from processing.infrastructure.proc_gauges import register_proc_gauges
from processing.infrastructure.telemetry import Telemetry, setup_telemetry


def create_app_from_environment() -> FastAPI:
    telemetry = setup_telemetry()
    app = create_app(partial(proc_services, ApiSettings(), telemetry))
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
async def proc_services(settings: ApiSettings, telemetry: Telemetry) -> AsyncIterator[Services]:
    pool = create_pool(settings.db)
    store = OracleQualityStore(
        pool, call_timeout_ms=settings.db.call_timeout_ms, tracer=telemetry.tracer
    )
    register_proc_gauges(telemetry.meter, store.latest_check_runs, asyncio.get_running_loop())
    try:
        async with PersistenceClient(
            str(settings.persistence.url),
            settings.persistence.timeout_seconds,
            telemetry=telemetry,
        ) as persistence:
            yield Services(
                is_ready=OracleHealth(
                    pool, call_timeout_ms=settings.db.call_timeout_ms
                ).is_reachable,
                get_quality_days=GetQualityDays(store),
                get_value_quality=GetValueQuality(store),
                get_measures=GetMeasures(persistence, store),
            )
    finally:
        await asyncio.to_thread(telemetry.shutdown)
        await pool.close()
