import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext
from starlette.types import Receive, Scope, Send

from ingestion.facade.rest.app import Services, create_app
from tests.stub_run_history import StubRunHistory

TRACE_ID = 0x0AF7651916CD43DD8448EB211C80319C
TRACE_ID_HEX = "0af7651916cd43dd8448eb211c80319c"


async def _reachable() -> bool:
    return True


async def _unreachable() -> bool:
    return False


@asynccontextmanager
async def _services() -> AsyncIterator[Services]:
    runs = StubRunHistory()
    yield Services(_reachable, runs, runs)


def _client(is_ready: Callable[[], Awaitable[bool]] = _reachable) -> TestClient:
    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        runs = StubRunHistory()
        yield Services(is_ready, runs, runs)

    return TestClient(create_app(services))


def _app_that_fails() -> FastAPI:
    app = create_app(_services)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("ORA-00942: table SECRET_TABLE does not exist")

    return app


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


def test_an_unexpected_error_is_a_generic_problem(caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(_app_that_fails(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR), client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.text == (
        '{"type":"about:blank","title":"Internal server error","status":500,'
        '"detail":"An unexpected error occurred."}'
    )
    assert "ORA-00942" not in response.text
    assert "RuntimeError" not in response.text
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError
    assert record.event == "unexpected_error"  # type: ignore[attr-defined]


def test_an_unexpected_error_carries_the_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    app = _app_that_fails()

    async def traced(scope: Scope, receive: Receive, send: Send) -> None:
        span = NonRecordingSpan(
            SpanContext(trace_id=TRACE_ID, span_id=0xB7AD6B7169203331, is_remote=False)
        )
        with trace.use_span(span):
            await app(scope, receive, send)

    client = TestClient(traced, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR), client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["trace_id"] == TRACE_ID_HEX
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.trace_id == TRACE_ID_HEX  # type: ignore[attr-defined]
