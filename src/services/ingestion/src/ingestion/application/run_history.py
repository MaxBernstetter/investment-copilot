"""Use case: list run attempts newest first, page them by cursor, and read one run."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from ingestion.domain.run import RunAttempt


class RunHistory(Protocol):
    async def list_attempts(
        self,
        *,
        started_from: datetime | None,
        started_before: datetime | None,
        before_attempt_id: int | None,
        limit: int,
    ) -> Sequence[RunAttempt]:
        """Attempts newest first, with ``started_at`` in ``[started_from, started_before)``."""
        ...

    async def get_attempts(self, run_id: str) -> Sequence[RunAttempt]:
        """Every attempt of one run id, in attempt order."""
        ...


@dataclass(frozen=True, slots=True)
class RunsPage:
    attempts: tuple[RunAttempt, ...]
    next_cursor: int | None
    """``attempt_id`` of the last attempt in this page when more attempts follow."""


def _midnight_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


async def list_runs(
    history: RunHistory,
    *,
    from_date: date | None,
    to_date: date | None,
    before_attempt_id: int | None,
    limit: int,
) -> RunsPage:
    """One page of attempts; ``to_date`` is inclusive, so it is read up to the next midnight.

    The latest representable date has no upper bound (the next midnight does not exist).
    """
    started_from = None if from_date is None else _midnight_utc(from_date)
    started_before = None
    if to_date is not None and to_date < date.max:
        started_before = _midnight_utc(to_date + timedelta(days=1))
    rows = await history.list_attempts(
        started_from=started_from,
        started_before=started_before,
        before_attempt_id=before_attempt_id,
        limit=limit + 1,
    )
    kept = tuple(rows[:limit])
    more = len(rows) > limit
    next_cursor = kept[-1].attempt_id if more and kept else None
    return RunsPage(attempts=kept, next_cursor=next_cursor)
