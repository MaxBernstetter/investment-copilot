"""The alerts endpoint against a stub history and a fixed clock. No I/O."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunStatus
from ingestion.facade.rest.app import Services, create_app
from tests.stub_run_history import StubRunHistory

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def attempt(
    attempt_id: int,
    status: RunStatus,
    finished: datetime | None,
    *,
    operation: Operation = Operation.DAILY,
    error_message: str | None = "boom",
) -> RunAttempt:
    failed = status in (RunStatus.FAILED, RunStatus.PARTIAL)
    return RunAttempt(
        attempt_id=attempt_id,
        run_id=f"run-{attempt_id}",
        attempt=1,
        operation=operation,
        status=status,
        started_at=NOW - timedelta(days=30),
        finished_at=finished,
        counts=RunCounts(),
        error_type="SourceError" if failed else None,
        error_message=error_message if failed else None,
    )


def _client(runs: StubRunHistory) -> TestClient:
    @asynccontextmanager
    async def services() -> AsyncIterator[Services]:
        async def ready() -> bool:
            return True

        yield Services(ready, runs, runs, clock=lambda: NOW)

    return TestClient(create_app(services))


def test_alerts_returns_active_and_recently_cleared_alerts() -> None:
    runs = StubRunHistory(
        attempts=[
            attempt(1, RunStatus.FAILED, NOW - timedelta(days=1)),
            attempt(2, RunStatus.FAILED, NOW - timedelta(days=5), operation=Operation.HISTORY),
            attempt(3, RunStatus.SUCCEEDED, NOW - timedelta(days=3), operation=Operation.HISTORY),
        ]
    )

    with _client(runs) as client:
        response = client.get("/v1/alerts")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [row["alert_id"] for row in data] == ["run_failed-1", "run_failed-2"]
    active, cleared = data
    assert set(active) == {
        "alert_id",
        "name",
        "severity",
        "since",
        "cleared_at",
        "acknowledged_at",
        "run_id",
        "attempt",
        "cause",
    }
    assert active["name"] == "run_failed"
    assert active["severity"] == "critical"
    assert active["cleared_at"] is None
    assert active["acknowledged_at"] is None
    assert active["run_id"] == "run-1"
    assert active["attempt"] == 1
    assert active["cause"] == "SourceError: boom"
    assert cleared["cleared_at"] is not None
    assert runs.alert_calls == [NOW - timedelta(days=7)]


def test_alerts_is_empty_without_failures() -> None:
    with _client(StubRunHistory()) as client:
        response = client.get("/v1/alerts")

    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_a_long_cause_is_cut_to_the_contract_limit() -> None:
    runs = StubRunHistory(
        attempts=[attempt(1, RunStatus.FAILED, NOW - timedelta(days=1), error_message="x" * 5000)]
    )

    with _client(runs) as client:
        response = client.get("/v1/alerts")

    cause = response.json()["data"][0]["cause"]
    assert len(cause) == 4000
    assert cause.startswith("SourceError: x")
