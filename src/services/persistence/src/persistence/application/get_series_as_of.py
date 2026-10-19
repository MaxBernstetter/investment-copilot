"""Use case: read one published maturity of a curve over valid dates, as known at a time."""

from datetime import date, datetime, timedelta
from typing import Protocol

from persistence.domain.curve import FutureAsOfError, NothingKnownError
from persistence.domain.series import InvalidRangeError, Series, SeriesPoint

DEFAULT_RANGE = timedelta(days=365)
"""Length of the valid-date range when only the end is given."""

MAX_RANGE = timedelta(days=3660)
"""Longest valid-date range served in one read."""


class SeriesReader(Protocol):
    """Port to the bitemporal store: reads published series as of a knowledge time."""

    async def current_knowledge_time(self) -> datetime:
        """The knowledge time now, from the database clock (UTC)."""
        ...

    async def latest_valid_date(self, curve_id: str, as_of: datetime) -> date | None:
        """The latest valid date with a published value known at ``as_of``; None if none."""
        ...

    async def has_maturity(self, curve_id: str, maturity: str) -> bool:
        """Whether the maturity is on the grid of the curve; False if the curve is undefined."""
        ...

    async def series_as_of(
        self, curve_id: str, maturity: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[SeriesPoint]:
        """Published values known at ``as_of`` for the valid dates in the range, in date order."""
        ...


class GetSeriesAsOf:
    def __init__(self, reader: SeriesReader) -> None:
        self._reader = reader

    async def __call__(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date | None,
        valid_to: date | None,
        as_of: datetime | None,
    ) -> Series:
        now = await self._reader.current_knowledge_time()
        if as_of is None:
            as_of = now
        if as_of > now:
            raise FutureAsOfError(f"as_of {as_of.isoformat()} is in the future")

        if not await self._reader.has_maturity(curve_id, maturity):
            raise NothingKnownError(f"Maturity {maturity} is not on the grid of curve {curve_id}")

        if valid_to is None:
            valid_to = await self._reader.latest_valid_date(curve_id, as_of)
            if valid_to is None:
                raise NothingKnownError(
                    f"No published value of curve {curve_id} is known as of {as_of.isoformat()}"
                )
        if valid_from is None:
            valid_from = valid_to - DEFAULT_RANGE
        if valid_from > valid_to:
            raise InvalidRangeError(f"from {valid_from} is after to {valid_to}")
        if valid_to - valid_from > MAX_RANGE:
            raise InvalidRangeError(f"the range exceeds {MAX_RANGE.days} days")

        points = await self._reader.series_as_of(curve_id, maturity, valid_from, valid_to, as_of)
        if not points:
            raise NothingKnownError(
                f"Nothing is known about {maturity} of curve {curve_id} "
                f"from {valid_from} to {valid_to} as of {as_of.isoformat()}"
            )
        return Series(curve_id=curve_id, maturity=maturity, as_of=as_of, points=tuple(points))
