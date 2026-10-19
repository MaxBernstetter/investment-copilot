"""Knowledge time of a read: the requested as_of, capped at the knowledge horizon.

A read at or before the knowledge horizon gives the same answer forever, because
no later commit can get a knowledge time that early (ADR 0017). A later as_of is
therefore answered at the horizon, and the caller sees the time it was answered at.
"""

from datetime import datetime
from typing import Protocol

from persistence.domain.curve import FutureAsOfError


class KnowledgeReader(Protocol):
    """Port to the bitemporal store: the two clocks a read is resolved against."""

    async def current_knowledge_time(self) -> datetime:
        """The database clock now, in UTC."""
        ...

    async def knowledge_horizon(self) -> datetime:
        """The knowledge time of the latest committed write, in UTC."""
        ...


async def resolve_as_of(reader: KnowledgeReader, as_of: datetime | None) -> datetime:
    """The knowledge time to read at: the horizon if no as_of is given, else the earlier of both.

    Raises FutureAsOfError if as_of lies after the database clock.
    """
    if as_of is not None and as_of > await reader.current_knowledge_time():
        raise FutureAsOfError(f"as_of {as_of.isoformat()} is in the future")
    horizon = await reader.knowledge_horizon()
    return horizon if as_of is None else min(as_of, horizon)
