"""Use case: the values of a curve that changed between two knowledge times."""

from datetime import date, datetime
from typing import Protocol

from persistence.application.get_series_as_of import MAX_RANGE
from persistence.application.knowledge_time import resolve_as_of
from persistence.domain.changes import CurveChanges, ValueChange
from persistence.domain.curve import NothingKnownError
from persistence.domain.series import InvalidRangeError


class ChangeReader(Protocol):
    """Port to the bitemporal store: reads the changes of a curve between two knowledge times."""

    async def current_knowledge_time(self) -> datetime:
        """The knowledge time now, from the database clock (UTC)."""
        ...

    async def knowledge_horizon(self) -> datetime:
        """The committed knowledge horizon (UTC): the knowledge time of the latest commit."""
        ...

    async def has_curve(self, curve_id: str) -> bool:
        """Whether the curve is defined."""
        ...

    async def changes(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        since: datetime,
        as_of: datetime,
    ) -> list[ValueChange]:
        """Published values whose visible version at ``as_of`` differs from the one at ``since``."""
        ...


class GetCurveChanges:
    def __init__(self, reader: ChangeReader) -> None:
        self._reader = reader

    async def __call__(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        since: datetime,
        as_of: datetime | None,
    ) -> CurveChanges:
        since = await resolve_as_of(self._reader, since)
        as_of = await resolve_as_of(self._reader, as_of)

        if since > as_of:
            raise InvalidRangeError(f"since {since.isoformat()} is after as_of {as_of.isoformat()}")
        if valid_from > valid_to:
            raise InvalidRangeError(f"from {valid_from} is after to {valid_to}")
        if valid_to - valid_from > MAX_RANGE:
            raise InvalidRangeError(f"the range exceeds {MAX_RANGE.days} days")

        if not await self._reader.has_curve(curve_id):
            raise NothingKnownError(f"Curve {curve_id} is not defined")

        changes = await self._reader.changes(curve_id, valid_from, valid_to, since, as_of)
        return CurveChanges(
            curve_id=curve_id,
            valid_from=valid_from,
            valid_to=valid_to,
            since=since,
            as_of=as_of,
            changes=tuple(changes),
        )
