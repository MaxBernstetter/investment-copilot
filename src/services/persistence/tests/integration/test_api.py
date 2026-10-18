"""End to end: HTTP request -> facade -> use case -> Oracle adapter -> PL/SQL -> table."""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from typing import Any

import pytest
from contracts.persistence.v1 import RECORD_VERSIONS_PATH
from fastapi.testclient import TestClient

from persistence.api import oracle_services
from persistence.config import Settings
from persistence.facade.rest.app import create_app
from tests.integration.conftest import APP_PASSWORD, OracleDatabase, stored_versions


@pytest.fixture
def client(oracle: OracleDatabase) -> Iterator[TestClient]:
    settings = Settings(db_dsn=oracle.dsn, db_password=APP_PASSWORD)
    with TestClient(create_app(partial(oracle_services, settings))) as client:
        yield client


def batch(curve_id: str) -> dict[str, Any]:
    return {
        "observations": [
            {
                "curve_id": curve_id,
                "maturity": maturity,
                "valid_date": "2026-03-12",
                "value": value,
                "origin": "published",
                "source_id": "ecb",
                "run_id": "ingestion-ecb-2026-03-12",
                "change_reason": "initial",
            }
            for maturity, value in [("2Y", "2.10"), ("10Y", "2.61")]
        ]
    }


def test_records_a_batch_end_to_end(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    response = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    assert response.status_code == 200
    body = response.json()
    assert body["recorded_count"] == 2
    known_from = datetime.fromisoformat(body["known_from"])
    versions = stored_versions(oracle, curve_id)
    assert [(v["maturity"], v["value"]) for v in versions] == [("10Y", 2.61), ("2Y", 2.1)]
    assert {v["known_from"].replace(tzinfo=UTC) for v in versions} == {known_from}


def test_recording_an_open_observation_again_is_a_conflict(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert len(stored_versions(oracle, curve_id)) == 2


def test_is_live_and_ready(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json() == {"status": "ready"}
