from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any

import pytest
from contracts.persistence.v1 import (
    CURVE_CHANGES_PATH,
    CURVE_OBSERVATIONS_PATH,
    RECORD_VERSIONS_PATH,
    SERIES_OBSERVATIONS_PATH,
    VALUE_VERSIONS_PATH,
)
from fastapi.testclient import TestClient

from persistence.application.get_curve_as_of import GetCurveAsOf
from persistence.application.get_curve_changes import GetCurveChanges
from persistence.application.get_series_as_of import GetSeriesAsOf
from persistence.application.get_value_versions import GetValueVersions
from persistence.application.record_versions import RecordVersions
from persistence.domain.changes import ValueChange
from persistence.domain.observation import (
    ChangeReason,
    Observation,
    OpenVersionExistsError,
    RecordedVersions,
)
from persistence.domain.versions import ValueVersion
from persistence.facade.rest.app import Services, create_app
from tests.unit.fakes import GRID, FakeCurveReader, InMemoryObservationRepository


def observation(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "curve_id": "ecb-aaa-spot",
        "maturity": "10Y",
        "valid_date": "2026-03-12",
        "value": 2.61,
        "origin": "published",
        "source_id": "ecb",
        "run_id": "ingestion-ecb-2026-03-12",
        "change_reason": "initial",
    }
    return fields | overrides


class FakeBackend:
    def __init__(self) -> None:
        self.repository = InMemoryObservationRepository()
        self.curves = FakeCurveReader()
        self.is_database_reachable = True

    async def is_ready(self) -> bool:
        return self.is_database_reachable

    @asynccontextmanager
    async def services(self) -> AsyncIterator[Services]:
        yield Services(
            RecordVersions(self.repository),
            self.is_ready,
            GetCurveAsOf(self.curves),
            GetSeriesAsOf(self.curves),
            GetValueVersions(self.curves),
            GetCurveChanges(self.curves),
        )


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def client(backend: FakeBackend) -> Iterator[TestClient]:
    with TestClient(create_app(backend.services)) as client:
        yield client


def test_records_a_batch_and_returns_its_knowledge_time(
    client: TestClient, backend: FakeBackend
) -> None:
    batch = {
        "observations": [
            observation(maturity="2Y", normalization_version="1", delivery_id="delivery-1"),
            observation(maturity="10Y"),
        ]
    }

    response = client.post(RECORD_VERSIONS_PATH, json=batch)

    assert response.status_code == 200
    assert response.json() == {
        "recorded_count": 2,
        "unchanged_count": 0,
        "known_from": "2026-03-12T18:00:00Z",
    }
    assert [
        (stored.maturity, stored.normalization_version, stored.delivery_id)
        for stored, _ in backend.repository.versions
    ] == [("2Y", "1", "delivery-1"), ("10Y", None, None)]


def test_a_contract_violation_is_a_problem_response(
    client: TestClient, backend: FakeBackend
) -> None:
    response = client.post(RECORD_VERSIONS_PATH, json={"observations": [observation(value=None)]})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Invalid request"
    assert problem["errors"][0]["loc"] == ["body", "observations", 0, "value"]
    assert backend.repository.versions == []


def test_a_batch_with_duplicate_observations_is_rejected(client: TestClient) -> None:
    response = client.post(
        RECORD_VERSIONS_PATH, json={"observations": [observation(), observation(value=2.7)]}
    )

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid observations"


def test_reports_unchanged_observations_of_a_reload(client: TestClient) -> None:
    client.post(RECORD_VERSIONS_PATH, json={"observations": [observation(maturity="2Y")]})
    reload = {"observations": [observation(maturity="2Y"), observation(maturity="10Y")]}

    response = client.post(RECORD_VERSIONS_PATH, json=reload)

    assert response.status_code == 200
    assert response.json()["recorded_count"] == 1
    assert response.json()["unchanged_count"] == 1


class LosesTheRace:
    """A store where a concurrent write always opened the version first."""

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        raise OpenVersionExistsError("a concurrent call opened a version first")


def test_a_concurrent_write_is_a_conflict() -> None:
    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        async def is_ready() -> bool:
            return True

        curves = FakeCurveReader()
        yield Services(
            RecordVersions(LosesTheRace()),
            is_ready,
            GetCurveAsOf(curves),
            GetSeriesAsOf(curves),
            GetValueVersions(curves),
            GetCurveChanges(curves),
        )

    with TestClient(create_app(services)) as client:
        response = client.post(RECORD_VERSIONS_PATH, json={"observations": [observation()]})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Concurrent write"


def test_health_reports_the_process_is_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_the_database_is_reachable(client: TestClient) -> None:
    assert client.get("/ready").status_code == 200


def test_not_ready_when_the_database_is_unreachable(
    client: TestClient, backend: FakeBackend
) -> None:
    backend.is_database_reachable = False

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


CURVE_PATH = CURVE_OBSERVATIONS_PATH.format(curve_id="ecb-aaa-spot")


def seed_curve(backend: FakeBackend, valid_date: date = date(2026, 3, 12)) -> None:
    backend.curves.values[("ecb-aaa-spot", valid_date)] = {"2Y": 2.10, "10Y": 2.61}


def expected_points(**values: float) -> list[dict[str, Any]]:
    return [
        {
            "maturity": maturity,
            "months": months,
            "value": values.get(maturity),
            "version_id": 1 if maturity in values else None,
        }
        for maturity, months in GRID
    ]


def test_returns_the_curve_as_of_the_given_time(client: TestClient, backend: FakeBackend) -> None:
    seed_curve(backend)

    response = client.get(
        CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": "2026-03-13T08:00:00Z"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_date": "2026-03-12",
            "points": expected_points(**{"2Y": 2.1, "10Y": 2.61}),
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z"},
    }


def test_without_as_of_echoes_the_knowledge_horizon(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(CURVE_PATH, params={"valid_date": "2026-03-12"})

    assert response.status_code == 200
    assert response.json()["meta"] == {"as_of": "2026-03-13T09:00:00Z"}


def test_without_valid_date_returns_the_latest_known_valid_date(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend, date(2026, 3, 12))
    seed_curve(backend, date(2026, 3, 13))

    response = client.get(CURVE_PATH)

    assert response.status_code == 200
    assert response.json()["data"]["valid_date"] == "2026-03-13"


def test_unknown_curve_is_a_not_found_problem(client: TestClient) -> None:
    response = client.get(
        CURVE_OBSERVATIONS_PATH.format(curve_id="unknown-curve"),
        params={"valid_date": "2026-03-12"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_future_as_of_is_an_invalid_request_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(
        CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": "2026-03-13T10:00:00Z"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid as_of"


def test_naive_as_of_is_an_invalid_request_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(
        CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": "2026-03-13T08:00:00"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"


SERIES_PATH = SERIES_OBSERVATIONS_PATH.format(curve_id="ecb-aaa-spot", maturity="10Y")


def test_curve_points_carry_the_version_id_of_the_visible_version(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)
    backend.curves.version_ids[("ecb-aaa-spot", "10Y", date(2026, 3, 12))] = 42

    response = client.get(
        CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": "2026-03-13T08:00:00Z"}
    )

    points = {point["maturity"]: point for point in response.json()["data"]["points"]}
    assert points["10Y"]["version_id"] == 42
    assert points["2Y"]["version_id"] == 1
    assert points["3M"]["value"] is None
    assert points["3M"]["version_id"] is None


def test_series_points_carry_the_version_id(client: TestClient, backend: FakeBackend) -> None:
    seed_curve(backend)
    backend.curves.version_ids[("ecb-aaa-spot", "10Y", date(2026, 3, 12))] = 42

    response = client.get(
        SERIES_PATH,
        params={"from": "2026-03-01", "to": "2026-03-12", "as_of": "2026-03-13T08:00:00Z"},
    )

    assert response.json()["data"]["points"] == [
        {"valid_date": "2026-03-12", "value": 2.61, "version_id": 42}
    ]


def test_returns_the_series_of_a_maturity_in_the_envelope(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(
        SERIES_PATH,
        params={"from": "2026-03-01", "to": "2026-03-12", "as_of": "2026-03-13T08:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "points": [{"valid_date": "2026-03-12", "value": 2.61, "version_id": 1}],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z"},
    }


def test_unknown_maturity_is_a_not_found_problem(client: TestClient, backend: FakeBackend) -> None:
    seed_curve(backend)

    response = client.get(
        SERIES_OBSERVATIONS_PATH.format(curve_id="ecb-aaa-spot", maturity="4Y"),
        params={"to": "2026-03-12"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_no_point_in_the_range_is_a_not_found_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(SERIES_PATH, params={"from": "2020-01-01", "to": "2020-12-31"})

    assert response.status_code == 404
    assert response.json()["title"] == "Not found"


def test_from_after_to_is_an_invalid_range_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(SERIES_PATH, params={"from": "2026-03-13", "to": "2026-03-12"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid range"


def test_future_as_of_on_a_series_is_an_invalid_as_of_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(SERIES_PATH, params={"as_of": "2026-03-13T10:00:00Z"})

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid as_of"


def test_a_malformed_range_date_is_an_invalid_request_problem(
    client: TestClient, backend: FakeBackend
) -> None:
    seed_curve(backend)

    response = client.get(SERIES_PATH, params={"from": "2026-13-01"})

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid request"


VERSIONS_PATH = VALUE_VERSIONS_PATH.format(
    curve_id="ecb-aaa-spot", maturity="10Y", valid_date="2026-03-12"
)


def test_value_versions_route_returns_the_envelope(
    client: TestClient, backend: FakeBackend
) -> None:
    backend.curves.versions[("ecb-aaa-spot", "10Y", date(2026, 3, 12))] = [
        ValueVersion(
            version_id=1,
            value=2.61,
            known_from=datetime(2026, 3, 12, 18, 0, tzinfo=UTC),
            known_to=None,
            source_id="ecb",
            run_id="ingestion-ecb-2026-03-12",
            change_reason=ChangeReason.INITIAL,
            normalization_version="1",
            delivery_id="delivery-1",
        )
    ]

    response = client.get(VERSIONS_PATH, params={"as_of": "2026-03-13T08:00:00Z"})

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "valid_date": "2026-03-12",
            "versions": [
                {
                    "version_id": 1,
                    "value": 2.61,
                    "known_from": "2026-03-12T18:00:00Z",
                    "known_to": None,
                    "source_id": "ecb",
                    "run_id": "ingestion-ecb-2026-03-12",
                    "change_reason": "initial",
                    "normalization_version": "1",
                    "delivery_id": "delivery-1",
                }
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z"},
    }


def test_value_versions_route_not_found_is_404(client: TestClient, backend: FakeBackend) -> None:
    seed_curve(backend)

    response = client.get(
        VALUE_VERSIONS_PATH.format(curve_id="ecb-aaa-spot", maturity="4Y", valid_date="2026-03-12")
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_value_versions_route_bad_date_is_422(client: TestClient) -> None:
    response = client.get(
        VALUE_VERSIONS_PATH.format(curve_id="ecb-aaa-spot", maturity="10Y", valid_date="2026-13-01")
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"


CHANGES_PATH = CURVE_CHANGES_PATH.format(curve_id="ecb-aaa-spot")


def test_changes_route_returns_the_envelope(client: TestClient, backend: FakeBackend) -> None:
    backend.curves.value_changes["ecb-aaa-spot"] = [
        ValueChange(
            valid_date=date(2026, 3, 12),
            maturity="10Y",
            old_value=2.61,
            new_value=2.7,
            change_reason=ChangeReason.CORRECTION,
            source_id="ecb",
            known_from=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
        )
    ]

    response = client.get(
        CHANGES_PATH,
        params={
            "from": "2026-03-01",
            "to": "2026-03-31",
            "since": "2026-03-12T18:00:00Z",
            "as_of": "2026-03-13T08:30:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_from": "2026-03-01",
            "valid_to": "2026-03-31",
            "changes": [
                {
                    "valid_date": "2026-03-12",
                    "maturity": "10Y",
                    "old_value": 2.61,
                    "new_value": 2.7,
                    "change_reason": "correction",
                    "source_id": "ecb",
                    "known_from": "2026-03-13T08:00:00Z",
                }
            ],
        },
        "meta": {"since": "2026-03-12T18:00:00Z", "as_of": "2026-03-13T08:30:00Z"},
    }


def test_changes_route_requires_since_from_and_to(client: TestClient) -> None:
    response = client.get(CHANGES_PATH, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    missing = {error["loc"][-1] for error in response.json()["errors"]}
    assert missing == {"since"}

    response = client.get(
        CHANGES_PATH, params={"since": "2026-03-12T18:00:00Z", "to": "2026-03-31"}
    )

    assert response.status_code == 422
    assert {error["loc"][-1] for error in response.json()["errors"]} == {"from"}


def test_changes_route_undefined_curve_is_404(client: TestClient) -> None:
    response = client.get(
        CURVE_CHANGES_PATH.format(curve_id="unknown-curve"),
        params={"from": "2026-03-01", "to": "2026-03-31", "since": "2026-03-12T18:00:00Z"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"


def test_changes_route_since_after_as_of_is_422(client: TestClient) -> None:
    response = client.get(
        CHANGES_PATH,
        params={
            "from": "2026-03-01",
            "to": "2026-03-31",
            "since": "2026-03-13T08:00:00Z",
            "as_of": "2026-03-12T18:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid range"
