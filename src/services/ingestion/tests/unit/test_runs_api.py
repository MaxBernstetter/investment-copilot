"""The run history endpoints against a stub history. No I/O."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunStatus
from ingestion.facade.rest.app import PROBLEM_JSON, Services, create_app
from tests.stub_run_history import StubRunHistory

RUN_ID = "daily_load_ecb-2026-10-16"
STARTED = datetime(2026, 10, 16, 13, 15, tzinfo=UTC)


def attempt(
    attempt_id: int,
    *,
    run_id: str = RUN_ID,
    number: int = 1,
    status: RunStatus = RunStatus.SUCCEEDED,
    started: datetime = STARTED,
    finished: datetime | None = STARTED + timedelta(seconds=90),
) -> RunAttempt:
    return RunAttempt(
        attempt_id=attempt_id,
        run_id=run_id,
        attempt=number,
        operation=Operation.DAILY,
        status=status,
        started_at=started,
        finished_at=finished,
        counts=RunCounts(66, 60, 6),
        error_type=None,
        error_message=None,
    )


def _client(runs: StubRunHistory) -> TestClient:
    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        async def ready() -> bool:
            return True

        yield Services(ready, runs)

    return TestClient(create_app(services))


def test_runs_are_listed_newest_first_as_transparency_runs() -> None:
    runs = StubRunHistory(attempts=[attempt(2), attempt(1)])

    with _client(runs) as client:
        response = client.get("/v1/runs")

    assert response.status_code == 200
    body = response.json()
    assert [row["service"] for row in body["data"]] == ["ingestion", "ingestion"]
    assert body["data"][0]["duration_seconds"] == 90.0
    assert runs.list_calls[0]["limit"] == 51
    assert runs.list_calls[0]["before_attempt_id"] is None


def test_a_full_page_has_a_cursor_to_the_next() -> None:
    runs = StubRunHistory(attempts=[attempt(3), attempt(2), attempt(1)])

    with _client(runs) as client:
        response = client.get("/v1/runs", params={"limit": 2})

    body = response.json()
    assert [row["run_id"] for row in body["data"]] == [RUN_ID, RUN_ID]
    assert len(body["data"]) == 2
    assert body["meta"]["next_cursor"] == "2"


def test_the_last_page_has_no_cursor() -> None:
    runs = StubRunHistory(attempts=[attempt(2), attempt(1)])

    with _client(runs) as client:
        response = client.get("/v1/runs", params={"limit": 2})

    assert len(response.json()["data"]) == 2
    assert response.json()["meta"]["next_cursor"] is None


def test_the_cursor_continues_before_its_attempt() -> None:
    runs = StubRunHistory(attempts=[attempt(16), attempt(15)])

    with _client(runs) as client:
        response = client.get("/v1/runs", params={"cursor": "17"})

    assert response.status_code == 200
    assert runs.list_calls[0]["before_attempt_id"] == 17


def test_from_and_to_are_inclusive_utc_dates() -> None:
    runs = StubRunHistory()

    with _client(runs) as client:
        response = client.get("/v1/runs", params={"from": "2026-10-16", "to": "2026-10-16"})

    assert response.status_code == 200
    assert runs.list_calls[0]["started_from"] == datetime(2026, 10, 16, tzinfo=UTC)
    assert runs.list_calls[0]["started_before"] == datetime(2026, 10, 17, tzinfo=UTC)


def test_from_after_to_is_a_problem() -> None:
    with _client(StubRunHistory()) as client:
        response = client.get("/v1/runs", params={"from": "2026-10-17", "to": "2026-10-16"})

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json()["detail"] == "`from` must not be after `to`."


@pytest.mark.parametrize(
    "params",
    [{"limit": "0"}, {"limit": "201"}, {"cursor": "abc"}, {"from": "16.10.2026"}],
)
def test_invalid_query_is_a_problem(params: dict[str, str]) -> None:
    with _client(StubRunHistory()) as client:
        response = client.get("/v1/runs", params=params)

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json()["title"] == "Invalid request"


def test_a_running_attempt_has_no_finish_or_duration() -> None:
    runs = StubRunHistory(
        attempts=[attempt(1, status=RunStatus.RUNNING, finished=None)],
    )

    with _client(runs) as client:
        response = client.get("/v1/runs")

    row = response.json()["data"][0]
    assert row["status"] == "running"
    assert row["finished_at"] is None
    assert row["duration_seconds"] is None


def test_a_run_lists_all_its_attempts_in_order() -> None:
    runs = StubRunHistory(
        attempts=[attempt(2, number=2), attempt(1, number=1)],
    )

    with _client(runs) as client:
        response = client.get(f"/v1/runs/{RUN_ID}")

    assert response.status_code == 200
    assert [row["attempt"] for row in response.json()["data"]] == [1, 2]
    assert runs.get_calls == [RUN_ID]


def test_an_unknown_run_is_a_404_problem() -> None:
    with _client(StubRunHistory()) as client:
        response = client.get("/v1/runs/no-such-run")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json()["title"] == "Run not found"
