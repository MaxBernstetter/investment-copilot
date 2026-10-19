"""Ports the use cases need from the outside world."""

from datetime import date, datetime
from typing import Protocol

from access.domain.curve import CurveAsOf
from access.domain.series import Series
from access.domain.versions import ValueVersions


class CurveReader(Protocol):
    """Reads one curve as of a knowledge time; ``None`` means the database clock."""

    async def curve_as_of(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf: ...

    async def series_as_of(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date | None,
        valid_to: date | None,
        as_of: datetime | None,
    ) -> Series:
        """Read one maturity over valid dates; ``None`` means the store's default."""
        ...

    async def value_versions(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime | None
    ) -> ValueVersions:
        """Read the version history of one value; ``None`` means the store's default."""
        ...
