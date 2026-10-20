"""Knowledge time of a quality read: the requested as_of or the database clock."""

from datetime import datetime
from typing import Protocol

from processing.domain.read import FutureAsOfError


class QualityClock(Protocol):
    async def current_time(self) -> datetime:
        """The database clock now, in UTC."""


async def resolve_as_of(clock: QualityClock, as_of: datetime | None) -> datetime:
    """The knowledge time to read at: now if no as_of is given, else the request.

    Raises FutureAsOfError if as_of lies after the database clock.
    """
    now = await clock.current_time()
    if as_of is not None and as_of > now:
        raise FutureAsOfError(f"as_of {as_of.isoformat()} is in the future")
    return now if as_of is None else as_of
