from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from processing.facade.rest.app import Services, create_app


async def _reachable() -> bool:
    return True


async def _unreachable() -> bool:
    return False


def _client(is_ready: Callable[[], Awaitable[bool]] = _reachable) -> TestClient:
    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        yield Services(is_ready)

    return TestClient(create_app(services))


def test_health_is_ok() -> None:
    with _client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_is_ok_when_the_database_answers() -> None:
    with _client(_reachable) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_is_503_when_the_database_is_unreachable() -> None:
    with _client(_unreachable) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
