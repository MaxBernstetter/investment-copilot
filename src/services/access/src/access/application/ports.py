"""Ports the use cases need from the outside world."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Protocol

from access.domain.catalogue import CurveDefinition
from access.domain.changes import CurveChanges
from access.domain.curve import CurveAsOf
from access.domain.measures import CurveMeasures
from access.domain.quality import ValueQuality
from access.domain.quality_checks import QualityCheckResult
from access.domain.quality_days import QualityDays
from access.domain.series import Series
from access.domain.versions import ValueVersions


class CatalogueReader(Protocol):
    """Reads the curve catalogue."""

    async def curves(self) -> tuple[CurveDefinition, ...]: ...


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

    async def changes(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        since: datetime,
        as_of: datetime | None,
    ) -> CurveChanges:
        """Read what changed in a curve between ``since`` and ``as_of``.

        ``None`` for ``as_of`` means the store's default.
        """
        ...


class QualityReader(Protocol):
    """Reads quality results for published values from the processing service."""

    async def value_quality(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        maturity: str | None,
        as_of: datetime,
    ) -> Mapping[int, ValueQuality] | None:
        """Quality per ``version_id``; ``None`` when processing is unavailable."""
        ...

    async def quality_days(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> QualityDays:
        """Quality per valid date; raises when processing rejects the query."""
        ...


class MeasuresReader(Protocol):
    """Reads derived measures of a curve from the processing service."""

    async def measures(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> CurveMeasures:
        """Measures per valid date; raises when processing rejects the query or cannot answer."""
        ...


class QualityChecker(Protocol):
    """Starts a quality check in the processing service and waits for its result."""

    async def check(self, curve_id: str, valid_from: date, valid_to: date) -> QualityCheckResult:
        """Check the range now; raises when processing rejects the request or cannot answer."""
        ...
