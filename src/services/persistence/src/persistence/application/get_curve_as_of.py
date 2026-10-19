"""Use case: read one published curve as it was known at a knowledge time."""

from datetime import date, datetime
from typing import Protocol

from persistence.application.knowledge_time import resolve_as_of
from persistence.domain.curve import CurveAsOf, CurvePoint, NothingKnownError


class CurveReader(Protocol):
    """Port to the bitemporal store: reads published curves as of a knowledge time."""

    async def current_knowledge_time(self) -> datetime:
        """The knowledge time now, from the database clock (UTC)."""
        ...

    async def knowledge_horizon(self) -> datetime:
        """The committed knowledge horizon (UTC): the knowledge time of the latest commit."""
        ...

    async def latest_valid_date(self, curve_id: str, as_of: datetime) -> date | None:
        """The latest valid date with a published value known at ``as_of``; None if none."""
        ...

    async def points_as_of(
        self, curve_id: str, valid_date: date, as_of: datetime
    ) -> list[CurvePoint]:
        """Every grid point of the curve for one valid date, in grid order; empty if undefined."""
        ...


class GetCurveAsOf:
    def __init__(self, reader: CurveReader) -> None:
        self._reader = reader

    async def __call__(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf:
        as_of = await resolve_as_of(self._reader, as_of)

        if valid_date is None:
            valid_date = await self._reader.latest_valid_date(curve_id, as_of)
            if valid_date is None:
                raise NothingKnownError(
                    f"No published value of curve {curve_id} is known as of {as_of.isoformat()}"
                )

        points = await self._reader.points_as_of(curve_id, valid_date, as_of)
        if all(point.value is None for point in points):
            raise NothingKnownError(
                f"Nothing is known about curve {curve_id} for {valid_date} "
                f"as of {as_of.isoformat()}"
            )
        return CurveAsOf(
            curve_id=curve_id, valid_date=valid_date, as_of=as_of, points=tuple(points)
        )
