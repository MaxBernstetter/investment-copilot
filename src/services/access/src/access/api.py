"""Composition root of the ``api`` process: wires the persistence client into the REST facade.

Run with: ``uvicorn --factory access.api:create_app_from_environment``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from access.application.catalogue import CachedCatalogue
from access.config import Settings
from access.facade.rest.app import Services, create_app
from access.infrastructure.persistence import PersistenceClient
from access.infrastructure.processing import ProcessingClient


def create_app_from_environment() -> FastAPI:
    settings = Settings()
    return create_app(
        partial(persistence_services, settings), cors_origins=settings.cors_origin_list()
    )


@asynccontextmanager
async def persistence_services(settings: Settings) -> AsyncIterator[Services]:
    async with (
        PersistenceClient(
            str(settings.persistence_url), settings.persistence_timeout_seconds
        ) as persistence,
        ProcessingClient(
            str(settings.processing_url),
            settings.processing_timeout_seconds,
            check_timeout_seconds=settings.quality_check_timeout_seconds,
        ) as quality,
    ):
        yield Services(
            persistence.is_ready,
            persistence,
            quality,
            CachedCatalogue(persistence, settings.catalogue_ttl_seconds),
            measures=quality,
            quality_checker=quality if settings.allow_quality_checks else None,
        )
