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
                "normalization_version": "1",
                "delivery_id": "delivery-1",
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
    assert [
        (v["maturity"], v["value"], v["normalization_version"], v["delivery_id"]) for v in versions
    ] == [
        ("10Y", 2.61, "1", "delivery-1"),
        ("2Y", 2.1, "1", "delivery-1"),
    ]
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


@pytest.mark.parametrize(
    ("maturity", "defined"), [("4Y", True), ("10Y", False)], ids=["off-grid", "undefined-curve"]
)
def test_rejects_an_observation_off_the_grid_and_stores_nothing(
    client: TestClient, oracle: OracleDatabase, curve_id: str, maturity: str, defined: bool
) -> None:
    request = batch(curve_id)
    off_grid = request["observations"][0] | {"maturity": maturity}
    if not defined:
        off_grid["curve_id"] = f"{curve_id}-undefined"[:64]
    request["observations"].append(off_grid)

    response = client.post(RECORD_VERSIONS_PATH, json=request)

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid observations"
    assert stored_versions(oracle, curve_id) == []


def test_is_live_and_ready(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json() == {"status": "ready"}
