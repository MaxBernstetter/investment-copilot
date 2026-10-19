"""Composition root of the ``api`` process: wires the persistence client into the REST facade.

Run with: ``uvicorn --factory access.api:create_app_from_environment``
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from access.config import Settings
from access.facade.rest.app import Services, create_app
from access.infrastructure.persistence import PersistenceClient


def create_app_from_environment() -> FastAPI:
    settings = Settings()
    return create_app(
        partial(persistence_services, settings), cors_origins=settings.cors_origin_list()
    )


@asynccontextmanager
async def persistence_services(settings: Settings) -> AsyncIterator[Services]:
    async with PersistenceClient(
        str(settings.persistence_url), settings.persistence_timeout_seconds
    ) as client:
        yield Services(client.is_ready, client)
