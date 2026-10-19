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

OPEN = datetime(9999, 12, 31)


@pytest.fixture
def client(oracle: OracleDatabase) -> Iterator[TestClient]:
    settings = Settings(db_dsn=oracle.dsn, db_password=APP_PASSWORD)
    with TestClient(create_app(partial(oracle_services, settings))) as client:
        yield client


def batch(
    curve_id: str, ten_year: str = "2.61", run_id: str = "ingestion-ecb-2026-03-12"
) -> dict[str, Any]:
    return {
        "observations": [
            {
                "curve_id": curve_id,
                "maturity": maturity,
                "valid_date": "2026-03-12",
                "value": value,
                "origin": "published",
                "source_id": "ecb",
                "run_id": run_id,
                "change_reason": "initial",
            }
            for maturity, value in [("2Y", "2.10"), ("10Y", ten_year)]
        ]
    }


def test_records_a_batch_end_to_end(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    response = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    assert response.status_code == 200
    body = response.json()
    assert (body["recorded_count"], body["unchanged_count"]) == (2, 0)
    known_from = datetime.fromisoformat(body["known_from"])
    versions = stored_versions(oracle, curve_id)
    assert [(v["maturity"], v["value"]) for v in versions] == [("10Y", 2.61), ("2Y", 2.1)]
    assert {v["known_from"].replace(tzinfo=UTC) for v in versions} == {known_from}


def test_an_unchanged_reload_succeeds_without_new_versions(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.post(
        RECORD_VERSIONS_PATH, json=batch(curve_id, run_id="ingestion-ecb-2026-03-13")
    )

    assert response.status_code == 200
    assert (response.json()["recorded_count"], response.json()["unchanged_count"]) == (0, 2)
    assert len(stored_versions(oracle, curve_id)) == 2


def test_a_revised_value_becomes_a_new_version_and_keeps_the_previous_one(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70"))

    assert response.status_code == 200
    assert (response.json()["recorded_count"], response.json()["unchanged_count"]) == (1, 1)
    versions = stored_versions(oracle, curve_id)
    assert [(v["maturity"], v["value"], v["known_to"] == OPEN) for v in versions] == [
        ("10Y", 2.61, False),
        ("10Y", 2.7, True),
        ("2Y", 2.1, True),
    ]


def test_is_live_and_ready(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json() == {"status": "ready"}
