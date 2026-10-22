"""End to end: HTTP request -> facade -> use case -> Oracle adapter -> PL/SQL -> table."""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from typing import Any

import pytest
from contracts.persistence.v1 import (
    CURVE_CHANGES_PATH,
    CURVE_OBSERVATIONS_PATH,
    CURVES_PATH,
    RECORD_VERSIONS_PATH,
    SERIES_OBSERVATIONS_PATH,
    VALUE_VERSIONS_PATH,
)
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
    curve_id: str,
    ten_year: str = "2.61",
    run_id: str = "ingestion-ecb-2026-03-12",
    change_reason: str = "initial",
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
                "change_reason": change_reason,
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


def test_a_revised_value_is_stored_as_revision(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70"))

    assert response.status_code == 200
    versions = stored_versions(oracle, curve_id)
    assert [(v["maturity"], v["value"], v["change_reason"]) for v in versions] == [
        ("10Y", 2.61, "initial"),
        ("10Y", 2.7, "revision"),
        ("2Y", 2.1, "initial"),
    ]


def test_rejects_a_scenario_value_on_a_real_curve_and_stores_nothing(
    client: TestClient, oracle: OracleDatabase, curve_id: str
) -> None:
    request = batch(curve_id)
    request["observations"][0]["source_id"] = "scenario"

    response = client.post(RECORD_VERSIONS_PATH, json=request)

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid observations"
    assert stored_versions(oracle, curve_id) == []


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


def curve_path(curve_id: str) -> str:
    return CURVE_OBSERVATIONS_PATH.format(curve_id=curve_id)


def ten_year_at(client: TestClient, curve_id: str, as_of: str) -> float | None:
    response = client.get(curve_path(curve_id), params={"valid_date": "2026-03-12", "as_of": as_of})
    assert response.status_code == 200
    (point,) = [p for p in response.json()["data"]["points"] if p["maturity"] == "10Y"]
    value: float | None = point["value"]
    return value


def test_reads_a_curve_before_and_after_a_revision(client: TestClient, curve_id: str) -> None:
    first = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id)).json()["known_from"]
    second = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70")).json()[
        "known_from"
    ]

    assert ten_year_at(client, curve_id, first) == 2.61
    assert ten_year_at(client, curve_id, second) == 2.7


def test_a_past_as_of_gives_a_repeatable_answer(client: TestClient, curve_id: str) -> None:
    first = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id)).json()["known_from"]
    params = {"valid_date": "2026-03-12", "as_of": first}
    before = client.get(curve_path(curve_id), params=params).json()

    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70"))

    assert client.get(curve_path(curve_id), params=params).json() == before


def test_reads_the_latest_curve_without_parameters(client: TestClient, curve_id: str) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.get(curve_path(curve_id))

    assert response.status_code == 200
    assert response.json()["data"]["valid_date"] == "2026-03-12"
    assert response.json()["meta"]["as_of"]


def test_the_default_as_of_is_the_last_committed_knowledge_time(
    client: TestClient, curve_id: str
) -> None:
    known_from = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id)).json()["known_from"]

    response = client.get(curve_path(curve_id), params={"valid_date": "2026-03-12"})

    assert datetime.fromisoformat(response.json()["meta"]["as_of"]) == datetime.fromisoformat(
        known_from
    )


def test_unknown_curve_is_not_found(client: TestClient, curve_id: str) -> None:
    response = client.get(curve_path(f"{curve_id}-undefined"))

    assert response.status_code == 404
    assert response.json()["title"] == "Not found"


def test_future_as_of_is_rejected(client: TestClient, curve_id: str) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.get(
        curve_path(curve_id), params={"as_of": "2100-01-01T00:00:00Z", "valid_date": "2026-03-12"}
    )

    assert response.status_code == 422
    assert response.json()["title"] == "Invalid as_of"


def series_path(curve_id: str) -> str:
    return SERIES_OBSERVATIONS_PATH.format(curve_id=curve_id, maturity="10Y")


def ten_year_series_at(client: TestClient, curve_id: str, as_of: str) -> list[tuple[str, float]]:
    response = client.get(
        series_path(curve_id),
        params={"from": "2026-03-12", "to": "2026-03-12", "as_of": as_of},
    )
    assert response.status_code == 200
    return [(point["valid_date"], point["value"]) for point in response.json()["data"]["points"]]


def test_reads_a_series_before_and_after_a_revision(client: TestClient, curve_id: str) -> None:
    first = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id)).json()["known_from"]
    second = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70")).json()[
        "known_from"
    ]

    assert ten_year_series_at(client, curve_id, first) == [("2026-03-12", 2.61)]
    assert ten_year_series_at(client, curve_id, second) == [("2026-03-12", 2.7)]


def test_a_past_series_as_of_gives_a_repeatable_answer(client: TestClient, curve_id: str) -> None:
    first = client.post(RECORD_VERSIONS_PATH, json=batch(curve_id)).json()["known_from"]
    before = ten_year_series_at(client, curve_id, first)

    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id, ten_year="2.70"))

    assert ten_year_series_at(client, curve_id, first) == before


def test_a_maturity_off_the_grid_is_not_found(client: TestClient, curve_id: str) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))

    response = client.get(
        SERIES_OBSERVATIONS_PATH.format(curve_id=curve_id, maturity="4Y"),
        params={"to": "2026-03-12"},
    )

    assert response.status_code == 404


def test_lists_both_versions_of_a_corrected_value(client: TestClient, curve_id: str) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))
    client.post(
        RECORD_VERSIONS_PATH,
        json=batch(curve_id, ten_year="2.70", change_reason="correction"),
    )

    response = client.get(
        VALUE_VERSIONS_PATH.format(curve_id=curve_id, maturity="10Y", valid_date="2026-03-12")
    )

    assert response.status_code == 200
    versions = response.json()["data"]["versions"]
    assert [(v["value"], v["change_reason"]) for v in versions] == [
        (2.61, "initial"),
        (2.7, "correction"),
    ]
    assert versions[0]["known_to"] == versions[1]["known_from"]
    assert versions[1]["known_to"] is None


def test_lists_the_change_of_a_corrected_value(client: TestClient, curve_id: str) -> None:
    client.post(RECORD_VERSIONS_PATH, json=batch(curve_id))
    since = client.get(curve_path(curve_id), params={"valid_date": "2026-03-12"}).json()["meta"][
        "as_of"
    ]
    client.post(
        RECORD_VERSIONS_PATH,
        json=batch(curve_id, ten_year="2.70", change_reason="correction"),
    )

    response = client.get(
        CURVE_CHANGES_PATH.format(curve_id=curve_id),
        params={"from": "2026-03-12", "to": "2026-03-12", "since": since},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["since"] == since
    assert [
        (c["maturity"], c["old_value"], c["new_value"], c["change_reason"])
        for c in body["data"]["changes"]
    ] == [("10Y", 2.61, 2.7, "correction")]


def test_lists_the_curve_catalogue(client: TestClient, curve_id: str) -> None:
    response = client.get(CURVES_PATH)

    assert response.status_code == 200
    data = response.json()["data"]
    ids = [curve["curve_id"] for curve in data]
    assert ids == sorted(ids)
    assert curve_id in ids
    simulated = next(curve for curve in data if curve["curve_id"] == "ecb-aaa-spot-sim")
    assert simulated["simulated"] is True
    assert simulated["source_id"] == "scenario"
    assert simulated["attribution"] == "Simulated scenario based on ECB statistics"
    assert simulated["source_model"] is None
    assert [m["months"] for m in simulated["maturities"]] == [
        3, 6, 12, 24, 36, 60, 84, 120, 180, 240, 360
    ]  # fmt: skip
