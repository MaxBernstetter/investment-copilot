"""Use case: quality of each business day of a curve as known at a time."""

from collections import defaultdict
from datetime import date, datetime
from typing import Protocol

from processing.application.check_quality import UnknownCurveError
from processing.application.knowledge_time import resolve_as_of
from processing.domain.assessment import CheckedDay
from processing.domain.quality import Finding
from processing.domain.read import (
    MAX_DAYS_RANGE,
    InvalidRangeError,
    QualityDayResult,
    QualityDays,
    checked_day,
    unchecked_day,
)
from processing.domain.rule_config import RULES_BY_CURVE


class QualityReader(Protocol):
    async def current_time(self) -> datetime:
        """The database clock now, in UTC."""

    async def checked_days(
        self, curve_id: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[CheckedDay]:
        """Latest checked day per valid date known at ``as_of``."""

    async def findings(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
    ) -> list[Finding]:
        """Findings from the same runs as ``checked_days``, for the range."""


class GetQualityDays:
    def __init__(self, reader: QualityReader) -> None:
        self._reader = reader

    async def __call__(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> QualityDays:
        rules = RULES_BY_CURVE.get(curve_id)
        if rules is None:
            raise UnknownCurveError(curve_id)
        as_of = await resolve_as_of(self._reader, as_of)
        if valid_from > valid_to:
            raise InvalidRangeError(f"from {valid_from} is after to {valid_to}")
        if valid_to - valid_from > MAX_DAYS_RANGE:
            raise InvalidRangeError(f"the range exceeds {MAX_DAYS_RANGE.days} days")

        checked = await self._reader.checked_days(curve_id, valid_from, valid_to, as_of)
        findings = await self._reader.findings(curve_id, valid_from, valid_to, as_of)
        checked_by_date = {day.valid_date: day for day in checked}
        findings_by_day: dict[date, list[Finding]] = defaultdict(list)
        for finding in findings:
            findings_by_day[finding.valid_date].append(finding)

        days = tuple(
            _day(valid_date, checked_by_date.get(valid_date), findings_by_day.get(valid_date, ()))
            for valid_date in rules.calendar.business_days(valid_from, valid_to)
        )
        return QualityDays(
            curve_id=curve_id,
            valid_from=valid_from,
            valid_to=valid_to,
            as_of=as_of,
            days=days,
        )


def _day(
    valid_date: date,
    checked: CheckedDay | None,
    findings: tuple[Finding, ...] | list[Finding],
) -> QualityDayResult:
    if checked is None:
        return unchecked_day(valid_date)
    return checked_day(
        valid_date,
        checked.status,
        checked.run_id,
        checked.checked_as_of,
        findings,
    )
