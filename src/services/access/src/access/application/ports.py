"""Ports the use cases need from the outside world."""

from datetime import date, datetime
from typing import Protocol

from access.domain.curve import CurveAsOf


class CurveReader(Protocol):
    """Reads one curve as of a knowledge time; ``None`` means the database clock."""

    async def curve_as_of(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf: ...
