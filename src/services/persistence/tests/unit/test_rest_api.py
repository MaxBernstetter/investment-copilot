from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import pytest
from contracts.persistence.v1 import RECORD_VERSIONS_PATH
from fastapi.testclient import TestClient

from persistence.application.record_versions import RecordVersions
from persistence.domain.observation import Observation, OpenVersionExistsError, RecordedVersions
from persistence.facade.rest.app import Services, create_app
from tests.unit.fakes import InMemoryObservationRepository


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
        self.is_database_reachable = True

    async def is_ready(self) -> bool:
        return self.is_database_reachable

    @asynccontextmanager
    async def services(self) -> AsyncIterator[Services]:
        yield Services(RecordVersions(self.repository), self.is_ready)


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
    batch = {"observations": [observation(maturity="2Y"), observation(maturity="10Y")]}

    response = client.post(RECORD_VERSIONS_PATH, json=batch)

    assert response.status_code == 200
    assert response.json() == {
        "recorded_count": 2,
        "unchanged_count": 0,
        "known_from": "2026-03-12T18:00:00Z",
    }
    assert [stored.maturity for stored, _ in backend.repository.versions] == ["2Y", "10Y"]


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

        yield Services(RecordVersions(LosesTheRace()), is_ready)

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
