"""End-to-end: the corrected-yield scenario, read back through the access api.

Needs the local stack (``task dev:reset`` then ``task dev:up``, from ``src/deploy``). Each
event runs the scenario job in the ``ingestion`` container. Runs in CI
(``.github/workflows/e2e.yml``) and locally with ``devbox run -- task dev:e2e``.
"""

import os
import subprocess
from typing import Any

import httpx
import pytest

ACCESS_URL = os.environ.get("E2E_ACCESS_URL", "http://localhost:8000")
E2E_COMPOSE_FILE = os.environ.get("E2E_COMPOSE_FILE")
SIM = "ecb-aaa-spot-sim"
REAL = "ecb-aaa-spot"
VALID_DATE = "2026-10-08"
PREVIOUS_DATE = "2026-10-07"
TIMEOUT_SECONDS = 10.0


def compose_command() -> list[str]:
    """``docker compose``, with an explicit file only when E2E_COMPOSE_FILE is set.

    Otherwise compose reads COMPOSE_FILE, which ``task dev:e2e`` sets (it adds the observability
    override while the profile runs, so the jobs get OTEL_*).
    """
    if E2E_COMPOSE_FILE:
        return ["docker", "compose", "-f", E2E_COMPOSE_FILE]
    return ["docker", "compose"]


def run_event(name: str) -> None:
    """Run one event of the corrected-yield scenario in the ingestion container."""
    subprocess.run(
        [
            *compose_command(),
            "--profile",
            "tools",
            "run",
            "--rm",
            "--build",
            "--entrypoint",
            "ingestion-scenario",
            "ingestion",
            "corrected-yield",
            "--event",
            name,
        ],
        check=True,
    )
    run_quality_check()


def run_quality_check() -> None:
    """Run the processing quality check for the scenario curve over the event window."""
    subprocess.run(
        [
            *compose_command(),
            "--profile",
            "tools",
            "run",
            "--rm",
            "--build",
            "processing-job",
            "ecb-aaa-spot-sim",
            "--from",
            "2026-10-05",
            "--to",
            "2026-10-08",
        ],
        check=True,
    )


def body(response: httpx.Response) -> dict[str, Any]:
    """The JSON body of a response."""
    return dict(response.json())


def value_of(payload: dict[str, Any], maturity: str) -> float | None:
    """The yield of one maturity in a curve observation body."""
    for point in payload["data"]["points"]:
        if point["maturity"] == maturity:
            value: float | None = point["value"]
            return value
    raise AssertionError(f"no point for maturity {maturity}")


def quality_of(payload: dict[str, Any], maturity: str) -> dict[str, Any]:
    """The quality object of one maturity in a curve observation body."""
    for point in payload["data"]["points"]:
        if point["maturity"] == maturity:
            quality: dict[str, Any] = point["quality"]
            return quality
    raise AssertionError(f"no point for maturity {maturity}")


def curve_path(curve_id: str) -> str:
    return f"/v1/curves/{curve_id}/observations"


def versions_path(curve_id: str, maturity: str, valid_date: str) -> str:
    return f"/v1/curves/{curve_id}/maturities/{maturity}/observations/{valid_date}/versions"


def quality_path(curve_id: str) -> str:
    return f"/v1/curves/{curve_id}/quality"


def measures_path(curve_id: str) -> str:
    return f"/v1/curves/{curve_id}/measures"


def point_input(payload: dict[str, Any], maturity: str) -> dict[str, Any]:
    """The measure input of one maturity in a measures body."""
    for item in payload["data"]["points"][0]["inputs"]:
        if item["maturity"] == maturity:
            input_: dict[str, Any] = item
            return input_
    raise AssertionError(f"no input for maturity {maturity}")


@pytest.fixture(scope="module")
def scenario_after_gap() -> None:
    """Publish and gap once; gap-day quality must be read before late-value arrives."""
    run_event("publish")
    run_event("gap")


def test_gap_day_quality_lists_missing_maturities_at_that_knowledge_time(
    scenario_after_gap: None,
) -> None:
    with httpx.Client(base_url=ACCESS_URL, timeout=TIMEOUT_SECONDS) as client:
        t_gap = body(client.get(curve_path(SIM), params={"valid_date": PREVIOUS_DATE}))["meta"][
            "as_of"
        ]
        response = client.get(
            quality_path(SIM),
            params={"from": "2026-10-05", "to": "2026-10-08", "as_of": t_gap},
        )
        assert response.status_code == 200
        days = {day["valid_date"]: day for day in body(response)["data"]["days"]}
        gap_day = days[PREVIOUS_DATE]
        assert gap_day["status"] == "warn"
        missing = [
            finding for finding in gap_day["findings"] if finding["rule"] == "missing-maturity"
        ]
        assert {finding["maturity"] for finding in missing} == {"10Y", "30Y"}


def test_past_view_is_reproduced_exactly_after_a_correction(scenario_after_gap: None) -> None:
    for event in ("bad-value", "late-value"):
        run_event(event)

    with httpx.Client(base_url=ACCESS_URL, timeout=TIMEOUT_SECONDS) as client:
        latest = client.get(curve_path(SIM), params={"valid_date": VALID_DATE})
        assert latest.status_code == 200
        t1 = body(latest)["meta"]["as_of"]
        assert value_of(body(latest), "10Y") == 26.4
        latest_quality = quality_of(body(latest), "10Y")
        assert latest_quality["status"] == "warn"
        rules = {flag["rule"] for flag in latest_quality["flags"]}
        assert rules == {"range", "jump"}
        assert all(flag["explanation"] for flag in latest_quality["flags"])

        past = client.get(curve_path(SIM), params={"valid_date": VALID_DATE, "as_of": t1})
        assert past.status_code == 200
        assert "immutable" in past.headers["cache-control"]
        content = past.content
        etag = past.headers["etag"]

        measures_query = {"from": VALID_DATE, "to": VALID_DATE, "as_of": t1}
        measured = client.get(measures_path(SIM), params=measures_query)
        assert measured.status_code == 200
        assert "immutable" in measured.headers["cache-control"]
        measured_body = body(measured)
        assert measured_body["meta"]["method_version"] == "1"
        assert measured_body["meta"]["as_of"] == t1
        measured_point = measured_body["data"]["points"][0]
        assert measured_point["spread_2y_10y"] == pytest.approx(2442.0)
        assert measured_point["inverted"] is False
        assert measured_point["quality"] == {"status": "warn", "flagged": ["10Y"]}
        measures_content = measured.content
        measures_etag = measured.headers["etag"]
        bad_10y_version = point_input(measured_body, "10Y")["version_id"]

        run_event("correction")

        reproduced = client.get(curve_path(SIM), params={"valid_date": VALID_DATE, "as_of": t1})
        assert reproduced.status_code == 200
        assert reproduced.content == content
        assert reproduced.headers["etag"] == etag

        revalidated = client.get(
            curve_path(SIM),
            params={"valid_date": VALID_DATE, "as_of": t1},
            headers={"If-None-Match": etag},
        )
        assert revalidated.status_code == 304

        current = client.get(curve_path(SIM), params={"valid_date": VALID_DATE})
        assert value_of(body(current), "10Y") == 2.64
        assert quality_of(body(current), "10Y")["status"] == "passed"

        reproduced_measures = client.get(measures_path(SIM), params=measures_query)
        assert reproduced_measures.content == measures_content
        assert reproduced_measures.headers["etag"] == measures_etag

        current_measures = body(
            client.get(measures_path(SIM), params={"from": VALID_DATE, "to": VALID_DATE})
        )
        current_point = current_measures["data"]["points"][0]
        assert current_measures["meta"]["method_version"] == "1"
        assert current_point["spread_2y_10y"] == pytest.approx(66.0)
        assert current_point["quality"]["status"] == "passed"
        assert point_input(current_measures, "10Y")["version_id"] != bad_10y_version

        versions = client.get(versions_path(SIM, "10Y", VALID_DATE))
        assert versions.status_code == 200
        history = body(versions)["data"]["versions"]
        assert [version["change_reason"] for version in history] == ["initial", "correction"]
        assert all(version["source_id"] == "scenario" for version in history)

        previous = body(client.get(curve_path(SIM), params={"valid_date": PREVIOUS_DATE}))
        assert value_of(previous, "10Y") is not None
        assert value_of(previous, "30Y") is not None


def test_the_scenario_never_touches_the_real_curve() -> None:
    with httpx.Client(base_url=ACCESS_URL, timeout=TIMEOUT_SECONDS) as client:
        response = client.get(versions_path(REAL, "10Y", VALID_DATE))
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            history = body(response)["data"]["versions"]
            assert all(version["source_id"] != "scenario" for version in history)
