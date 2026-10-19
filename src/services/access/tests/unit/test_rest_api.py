from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from access.facade.rest.app import Services, create_app

FRONTEND_ORIGIN = "http://localhost:5173"


class FakeServices:
    def __init__(self) -> None:
        self.ready = True

    async def is_ready(self) -> bool:
        return self.ready

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Services]:
        yield Services(self.is_ready)


@pytest.fixture
def services() -> FakeServices:
    return FakeServices()


@pytest.fixture
def client(services: FakeServices) -> Iterator[TestClient]:
    with TestClient(create_app(services.open, cors_origins=[FRONTEND_ORIGIN])) as client:
        yield client


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_persistence_is_ready(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_persistence_is_not(client: TestClient, services: FakeServices) -> None:
    services.ready = False

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/ready",
        headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_cors_ignores_other_origins(client: TestClient) -> None:
    response = client.options(
        "/ready",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers
