"""The run list use case against a stub history. No I/O."""

from datetime import UTC, date, datetime

import pytest

from ingestion.application.run_history import list_runs
from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunStatus
from tests.stub_run_history import StubRunHistory

pytestmark = pytest.mark.anyio

STARTED = datetime(2026, 10, 16, 13, 15, tzinfo=UTC)


def attempt(attempt_id: int) -> RunAttempt:
    return RunAttempt(
        attempt_id=attempt_id,
        run_id="daily_load_ecb-2026-10-16",
        attempt=1,
        operation=Operation.DAILY,
        status=RunStatus.SUCCEEDED,
        started_at=STARTED,
        finished_at=STARTED,
        counts=RunCounts(),
        error_type=None,
        error_message=None,
    )


async def test_list_runs_asks_for_one_more_than_the_limit() -> None:
    history = StubRunHistory()

    await list_runs(
        history, from_date=date(2026, 10, 16), to_date=None, before_attempt_id=None, limit=50
    )

    assert history.list_calls == [
        {
            "started_from": datetime(2026, 10, 16, tzinfo=UTC),
            "started_before": None,
            "before_attempt_id": None,
            "limit": 51,
        }
    ]


async def test_the_latest_date_is_an_open_upper_bound() -> None:
    history = StubRunHistory()

    await list_runs(history, from_date=None, to_date=date.max, before_attempt_id=None, limit=50)

    assert history.list_calls[0]["started_before"] is None


async def test_list_runs_without_more_rows_has_no_cursor() -> None:
    history = StubRunHistory(attempts=[attempt(3), attempt(2)])

    page = await list_runs(history, from_date=None, to_date=None, before_attempt_id=None, limit=2)

    assert [row.attempt_id for row in page.attempts] == [3, 2]
    assert page.next_cursor is None
