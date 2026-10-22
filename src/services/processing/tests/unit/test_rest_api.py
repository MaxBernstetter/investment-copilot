import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial

import pytest
from contracts.processing.v1 import (
    MEASURES_PATH,
    QUALITY_DAYS_PATH,
    VALUE_QUALITY_PATH,
    MeasuresResponse,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.trace import SpanContext, SpanKind
from pydantic import SecretStr
from starlette.types import Receive, Scope, Send

from processing.api import create_app_from_environment, instrument_app, proc_services
from processing.application.get_measures import GetMeasures
from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.config import ApiSettings, DatabaseSettings, PersistenceSettings
from processing.domain.quality import Value
from processing.facade.rest.app import Services, create_app
from processing.infrastructure.telemetry import Telemetry
from tests.unit.fakes import (
    FakeMeasureQuality,
    FakeObservationReader,
    FakeQualityStore,
    job_telemetry,
)

HORIZON = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
KNOWN = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
MEASURE_DAY = date(2026, 10, 8)


async def _reachable() -> bool:
    return True


async def _unreachable() -> bool:
    return False


def _client(
    is_ready: Callable[[], Awaitable[bool]] = _reachable,
    store: FakeQualityStore | None = None,
    telemetry: Telemetry | None = None,
    observations: FakeObservationReader | None = None,
    measure_quality: FakeMeasureQuality | None = None,
) -> TestClient:
    quality_store = store or FakeQualityStore()
    observation_reader = observations or _observations()
    quality_reader = measure_quality or FakeMeasureQuality()

    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        yield Services(
            is_ready=is_ready,
            get_quality_days=GetQualityDays(quality_store),
            get_value_quality=GetValueQuality(quality_store),
            get_measures=GetMeasures(observation_reader, quality_reader),
        )

    app = create_app(services)
    if telemetry is not None:
        instrument_app(app, telemetry)
    return TestClient(app)


def _observations(*, unknown: bool = False) -> FakeObservationReader:
    return FakeObservationReader(
        horizon=HORIZON,
        versions=[
            (KNOWN, Value(1, "3M", MEASURE_DAY, Decimal("1.98"))),
            (KNOWN, Value(2, "2Y", MEASURE_DAY, Decimal("1.98"))),
            (KNOWN, Value(3, "5Y", MEASURE_DAY, Decimal("2.21"))),
            (KNOWN, Value(4, "10Y", MEASURE_DAY, Decimal("2.64"))),
        ],
        unknown=unknown,
    )


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
    settings = ApiSettings(
        db=DatabaseSettings(dsn="oracle.test:1521/FREEPDB1", password=SecretStr("x")),
        persistence=PersistenceSettings(url="http://persistence.test:8001"),
    )
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
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence.test:8001")
    monkeypatch.setattr(
        "processing.api.instrument_app", lambda app, telemetry: calls.append("instrumented")
    )

    create_app_from_environment()

    assert calls == ["instrumented"]


def _app_with_boom() -> FastAPI:
    quality_store = FakeQualityStore()

    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        yield Services(
            is_ready=_reachable,
            get_quality_days=GetQualityDays(quality_store),
            get_value_quality=GetValueQuality(quality_store),
            get_measures=GetMeasures(_observations(), FakeMeasureQuality()),
        )

    app = create_app(services)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("ORA-00942: table SECRET_TABLE does not exist")

    return app


def test_an_unexpected_error_is_a_generic_problem(caplog: pytest.LogCaptureFixture) -> None:
    with TestClient(_app_with_boom(), raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal server error",
        "status": 500,
        "detail": "An unexpected error occurred.",
    }
    assert "ORA-00942" not in response.text
    assert "RuntimeError" not in response.text
    records = [r for r in caplog.records if getattr(r, "event", None) == "unexpected_error"]
    assert len(records) == 1
    assert records[0].levelname == "ERROR"
    assert records[0].exc_info is not None
    assert records[0].exc_info[0] is RuntimeError


def test_an_unexpected_error_carries_the_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    app = _app_with_boom()
    span_context = SpanContext(
        trace_id=0x0AF7651916CD43DD8448EB211C80319C,
        span_id=0xB7AD6B7169203331,
        is_remote=False,
    )

    async def traced(scope: Scope, receive: Receive, send: Send) -> None:
        with trace.use_span(trace.NonRecordingSpan(span_context)):
            await app(scope, receive, send)

    with TestClient(traced, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["trace_id"] == trace_id
    records = [r for r in caplog.records if getattr(r, "event", None) == "unexpected_error"]
    assert len(records) == 1
    assert getattr(records[0], "trace_id", None) == trace_id


def _measures_query(**params: str) -> dict[str, str]:
    return {"from": "2026-10-08", "to": "2026-10-08"} | params


def _measures_path(curve_id: str = "ecb-aaa-spot") -> str:
    return MEASURES_PATH.format(curve_id=curve_id)


def test_measures_match_the_contract() -> None:
    with _client() as client:
        response = client.get(_measures_path(), params=_measures_query())

    assert response.status_code == 200
    body = response.json()
    parsed = MeasuresResponse.model_validate(body)
    assert parsed.meta.method_version == "1"
    point = parsed.data.points[0]
    assert len(point.inputs) == 4
    assert point.spread_2y_10y == 66.0
    assert point.curvature_2y_5y_10y == -20.0
    assert point.inverted is False


def test_measures_of_an_unknown_curve_are_404() -> None:
    with _client() as client:
        response = client.get(_measures_path("unknown-curve"), params=_measures_query())

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_measures_reject_from_after_to_with_422() -> None:
    with _client() as client:
        response = client.get(_measures_path(), params=_measures_query(**{"from": "2026-10-09"}))

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid range"


def test_measures_reject_more_than_3660_days_with_422() -> None:
    too_long_from = MEASURE_DAY - timedelta(days=3661)
    with _client() as client:
        response = client.get(
            _measures_path(),
            params=_measures_query(**{"from": too_long_from.isoformat()}),
        )

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid range"


def test_measures_reject_a_future_as_of_with_422() -> None:
    with _client() as client:
        response = client.get(
            _measures_path(), params=_measures_query(as_of="2026-10-09T09:00:00Z")
        )

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid as_of"


def test_measures_with_a_settled_as_of_are_immutable() -> None:
    with _client() as client:
        response = client.get(
            _measures_path(), params=_measures_query(as_of="2026-10-09T07:30:00Z")
        )

    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_measures_answer_304_for_a_matching_etag() -> None:
    with _client() as client:
        first = client.get(_measures_path(), params=_measures_query())
        etag = first.headers["etag"]
        second = client.get(
            _measures_path(), params=_measures_query(), headers={"If-None-Match": etag}
        )

    assert second.status_code == 304
