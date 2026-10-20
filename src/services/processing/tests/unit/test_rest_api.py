import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial

import pytest
from contracts.processing.v1 import QUALITY_DAYS_PATH, VALUE_QUALITY_PATH
from fastapi.testclient import TestClient
from opentelemetry.trace import SpanKind
from pydantic import SecretStr

from processing.api import create_app_from_environment, instrument_app, proc_services
from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.config import DatabaseSettings
from processing.facade.rest.app import Services, create_app
from processing.infrastructure.telemetry import Telemetry
from tests.unit.fakes import FakeQualityStore, job_telemetry


async def _reachable() -> bool:
    return True


async def _unreachable() -> bool:
    return False


def _client(
    is_ready: Callable[[], Awaitable[bool]] = _reachable,
    store: FakeQualityStore | None = None,
    telemetry: Telemetry | None = None,
) -> TestClient:
    quality_store = store or FakeQualityStore()

    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        yield Services(
            is_ready,
            GetQualityDays(quality_store),
            GetValueQuality(quality_store),
        )

    app = create_app(services)
    if telemetry is not None:
        instrument_app(app, telemetry)
    return TestClient(app)


def test_health_is_ok() -> None:
    with _client() as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ready_reflects_database_reachability() -> None:
    with _client(_reachable) as client:
        assert client.get("/ready").json() == {"status": "ready"}
    with _client(_unreachable) as client:
        assert client.get("/ready").status_code == 503


def test_quality_days_matches_the_contract() -> None:
    with _client() as client:
        response = client.get(
            QUALITY_DAYS_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2026-10-07", "to": "2026-10-07"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["days"][0]["findings"][0]["rule"] == "missing-date"
    assert re.fullmatch(r'"[0-9a-f]{32}"', response.headers["etag"])


def test_invalid_range_returns_a_problem() -> None:
    with _client() as client:
        response = client.get(
            QUALITY_DAYS_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2026-10-08", "to": "2026-10-07"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_quality_days_reject_more_than_366_days() -> None:
    with _client() as client:
        response = client.get(
            QUALITY_DAYS_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2025-01-01", "to": "2026-01-03"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_an_unknown_curve_is_404() -> None:
    with _client() as client:
        response = client.get(
            QUALITY_DAYS_PATH.format(curve_id="unknown-curve"),
            params={"from": "2026-10-07", "to": "2026-10-07"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_value_quality_endpoint_is_available() -> None:
    with _client() as client:
        response = client.get(
            VALUE_QUALITY_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2026-10-07", "to": "2026-10-07"},
        )

    assert response.status_code == 200


def test_meta_as_of_is_the_requested_as_of_or_the_database_time() -> None:
    with _client() as client:
        default = client.get(
            QUALITY_DAYS_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2026-10-07", "to": "2026-10-07"},
        )
        explicit = client.get(
            QUALITY_DAYS_PATH.format(curve_id="ecb-aaa-spot"),
            params={"from": "2026-10-07", "to": "2026-10-07", "as_of": "2026-10-09T07:30:00Z"},
        )

    assert default.status_code == 200
    assert default.json()["meta"]["as_of"] == "2026-10-09T08:00:00Z"
    assert explicit.status_code == 200
    assert explicit.json()["meta"]["as_of"] == "2026-10-09T07:30:00Z"


def test_fastapi_requests_are_traced() -> None:
    telemetry, spans, _ = job_telemetry()

    with _client(telemetry=telemetry) as client:
        assert client.get("/health").status_code == 200
    telemetry.tracer_provider.force_flush()

    servers = [span for span in spans.get_finished_spans() if span.kind is SpanKind.SERVER]
    assert len(servers) == 1
    telemetry.shutdown()


class _FakePool:
    async def close(self) -> None:
        return None


def test_the_lifespan_shuts_telemetry_down_after_the_spans_are_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, spans, _ = job_telemetry()
    shutdowns: list[bool] = []

    class RecordingTelemetry(Telemetry):
        def shutdown(self) -> None:
            shutdowns.append(True)
            super().shutdown()

    telemetry = RecordingTelemetry(base.tracer_provider, base.meter_provider)
    monkeypatch.setattr("processing.api.create_pool", lambda _settings: _FakePool())
    settings = DatabaseSettings(dsn="oracle.test:1521/FREEPDB1", password=SecretStr("x"))
    app = create_app(partial(proc_services, settings, telemetry))
    instrument_app(app, telemetry)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert shutdowns == [True]
    assert [span for span in spans.get_finished_spans() if span.kind is SpanKind.SERVER]


def test_the_factory_instruments_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setenv("PROCESSING_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("PROCESSING_DB__PASSWORD", "not-a-secret")
    monkeypatch.setattr(
        "processing.api.instrument_app", lambda app, telemetry: calls.append("instrumented")
    )

    create_app_from_environment()

    assert calls == ["instrumented"]
