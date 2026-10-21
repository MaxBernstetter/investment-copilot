"""Use case: list check runs newest first, page them by cursor, and read one run."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from processing.application.ports import CheckRunHistory
from processing.domain.check_run import CheckRunAttempt


@dataclass(frozen=True, slots=True)
class RunsPage:
    attempts: tuple[CheckRunAttempt, ...]
    next_cursor: int | None
    """``check_run_id`` of the last check run in this page when more follow."""


def _midnight_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


async def list_runs(
    history: CheckRunHistory,
    *,
    from_date: date | None,
    to_date: date | None,
    before_check_run_id: int | None,
    limit: int,
) -> RunsPage:
    """One page of check runs; ``to_date`` is inclusive, so it is read up to the next midnight.

    The latest representable date has no upper bound (the next midnight does not exist).
    """
    recorded_from = None if from_date is None else _midnight_utc(from_date)
    recorded_before = None
    if to_date is not None and to_date < date.max:
        recorded_before = _midnight_utc(to_date + timedelta(days=1))
    rows = await history.list_check_runs(
        recorded_from=recorded_from,
        recorded_before=recorded_before,
        before_check_run_id=before_check_run_id,
        limit=limit + 1,
    )
    kept = tuple(rows[:limit])
    more = len(rows) > limit
    next_cursor = kept[-1].check_run_id if more and kept else None
    return RunsPage(attempts=kept, next_cursor=next_cursor)
