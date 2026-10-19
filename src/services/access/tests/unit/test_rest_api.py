from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.facade.rest.app import Services, create_app

FRONTEND_ORIGIN = "http://localhost:5173"
CURVE_PATH = "/v1/curves/ecb-aaa-spot/observations"
AS_OF = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))


class FakeCurveReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date | None, datetime | None]] = []
        self.error: Exception | None = None

    async def curve_as_of(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf:
        self.calls.append((curve_id, valid_date, as_of))
        if self.error is not None:
            raise self.error
        return CurveAsOf(
            curve_id=curve_id,
            valid_date=date(2026, 3, 12),
            as_of=AS_OF,
            points=(
                CurvePoint(maturity="3M", months=3, value=None),
                CurvePoint(maturity="10Y", months=120, value=2.61),
            ),
        )


class FakeServices:
    def __init__(self) -> None:
        self.ready = True
        self.curves = FakeCurveReader()

    async def is_ready(self) -> bool:
        return self.ready

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Services]:
        yield Services(self.is_ready, self.curves)


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


def test_returns_the_curve_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(CURVE_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_date": "2026-03-12",
            "points": [
                {"maturity": "3M", "months": 3, "value": None},
                {"maturity": "10Y", "months": 120, "value": 2.61},
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z"},
    }


def test_passes_valid_date_and_as_of_to_persistence(
    client: TestClient, services: FakeServices
) -> None:
    client.get(CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": AS_OF.isoformat()})

    assert services.curves.calls == [("ecb-aaa-spot", date(2026, 3, 12), AS_OF)]


def test_without_parameters_persistence_gets_none(
    client: TestClient, services: FakeServices
) -> None:
    client.get(CURVE_PATH)

    assert services.curves.calls == [("ecb-aaa-spot", None, None)]


def test_not_found_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = CurveNotFoundError("no curve named ecb-aaa-spot")

    response = client.get(CURVE_PATH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not found",
        "status": 404,
        "detail": "no curve named ecb-aaa-spot",
    }


def test_invalid_query_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = InvalidCurveQueryError("valid_date is outside the window")

    response = client.get(CURVE_PATH)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    assert response.json()["detail"] == "valid_date is outside the window"


def test_unavailable_persistence_is_a_503_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = PersistenceUnavailableError()

    response = client.get(CURVE_PATH)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Service unavailable",
        "status": 503,
        "detail": "The curve store is not reachable; try again later.",
    }


def test_bad_parameters_are_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(CURVE_PATH, params={"valid_date": "abc"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["title"] == "Invalid request"
    assert services.curves.calls == []


def test_naive_as_of_is_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(CURVE_PATH, params={"as_of": "2026-03-13T09:00:00"})

    assert response.status_code == 422
    assert services.curves.calls == []


def test_only_get_is_allowed(client: TestClient) -> None:
    response = client.post(CURVE_PATH)

    assert response.status_code == 405
