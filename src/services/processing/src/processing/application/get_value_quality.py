"""Use case: quality of published values of a curve as known at a time."""

from collections import defaultdict
from datetime import date, datetime
from typing import Protocol

from processing.application.check_quality import UnknownCurveError
from processing.application.knowledge_time import resolve_as_of
from processing.domain.assessment import ValueStatus
from processing.domain.quality import Finding
from processing.domain.read import (
    MAX_VALUES_RANGE,
    CurveValueQualities,
    InvalidRangeError,
    ValueQualityResult,
)
from processing.domain.rule_config import RULES_BY_CURVE


class ValueQualityReader(Protocol):
    async def current_time(self) -> datetime:
        """The database clock now, in UTC."""

    async def value_statuses(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[ValueStatus]:
        """Latest value quality per published value known at ``as_of``."""

    async def findings(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[Finding]:
        """Findings from the same runs as ``value_statuses``."""


class GetValueQuality:
    def __init__(self, reader: ValueQualityReader) -> None:
        self._reader = reader

    async def __call__(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
        *,
        maturity: str | None = None,
    ) -> CurveValueQualities:
        if curve_id not in RULES_BY_CURVE:
            raise UnknownCurveError(curve_id)
        as_of = await resolve_as_of(self._reader, as_of)
        if valid_from > valid_to:
            raise InvalidRangeError(f"from {valid_from} is after to {valid_to}")
        if valid_to - valid_from > MAX_VALUES_RANGE:
            raise InvalidRangeError(f"the range exceeds {MAX_VALUES_RANGE.days} days")

        statuses = await self._reader.value_statuses(
            curve_id, valid_from, valid_to, as_of, maturity=maturity
        )
        findings = await self._reader.findings(
            curve_id, valid_from, valid_to, as_of, maturity=maturity
        )
        flags_by_value: dict[tuple[int, str, date], list[Finding]] = defaultdict(list)
        for finding in findings:
            if finding.version_id is not None and finding.maturity is not None:
                flags_by_value[(finding.version_id, finding.maturity, finding.valid_date)].append(
                    finding
                )

        values = tuple(
            ValueQualityResult(
                version_id=status.version_id,
                maturity=status.maturity,
                valid_date=status.valid_date,
                status=status.status,
                flags=tuple(
                    flags_by_value.get((status.version_id, status.maturity, status.valid_date), ())
                ),
            )
            for status in statuses
        )
        return CurveValueQualities(
            curve_id=curve_id,
            valid_from=valid_from,
            valid_to=valid_to,
            as_of=as_of,
            values=values,
        )
