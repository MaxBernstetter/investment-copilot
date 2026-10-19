import httpx
import pytest

from access.infrastructure.persistence import PersistenceClient

pytestmark = pytest.mark.anyio

BASE_URL = "http://persistence:8001"


def client_answering(handler: httpx.MockTransport) -> PersistenceClient:
    return PersistenceClient(BASE_URL, 5.0, transport=handler)


async def test_is_ready_when_persistence_answers_200() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ready"
        return httpx.Response(200, json={"status": "ready"})

    async with client_answering(httpx.MockTransport(answer)) as client:
        assert await client.is_ready() is True


async def test_is_not_ready_when_persistence_answers_503() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "unavailable"})

    async with client_answering(httpx.MockTransport(answer)) as client:
        assert await client.is_ready() is False


async def test_is_not_ready_when_persistence_is_unreachable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        assert await client.is_ready() is False
