"""The check run list use case against a stub history. No I/O."""

from datetime import UTC, date, datetime

import pytest

from processing.application.run_history import list_runs
from processing.domain.check_run import CheckRunAttempt
from tests.unit.fakes import StubCheckRunHistory

pytestmark = pytest.mark.anyio

RECORDED = datetime(2026, 10, 16, 13, 15, tzinfo=UTC)


def attempt(check_run_id: int) -> CheckRunAttempt:
    return CheckRunAttempt(
        check_run_id=check_run_id,
        run_id="check-quality-ecb-aaa-spot-sim-2026-10-05-2026-10-08",
        attempt=1,
        recorded_at=RECORDED,
        value_count=2,
    )


async def test_list_runs_asks_for_one_more_than_the_limit() -> None:
    history = StubCheckRunHistory()

    await list_runs(
        history, from_date=date(2026, 10, 16), to_date=None, before_check_run_id=None, limit=50
    )

    assert history.list_calls == [
        {
            "recorded_from": datetime(2026, 10, 16, tzinfo=UTC),
            "recorded_before": None,
            "before_check_run_id": None,
            "limit": 51,
        }
    ]


async def test_the_latest_date_is_an_open_upper_bound() -> None:
    history = StubCheckRunHistory()

    await list_runs(history, from_date=None, to_date=date.max, before_check_run_id=None, limit=50)

    assert history.list_calls[0]["recorded_before"] is None


async def test_list_runs_without_more_rows_has_no_cursor() -> None:
    history = StubCheckRunHistory(attempts=[attempt(3), attempt(2)])

    page = await list_runs(history, from_date=None, to_date=None, before_check_run_id=None, limit=2)

    assert [row.check_run_id for row in page.attempts] == [3, 2]
    assert page.next_cursor is None
