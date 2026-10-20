"""Assess one chunk of a curve: combine plausibility and completeness into statuses."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from processing.domain.calendar import target_business_days
from processing.domain.completeness import check_completeness
from processing.domain.plausibility import check_jumps, check_range
from processing.domain.quality import Finding, Status, Value, worst
from processing.domain.rule_config import RULE_SET_VERSION, PlausibilityThresholds


@dataclass(frozen=True, slots=True)
class DayStatus:
    valid_date: date
    status: Status


@dataclass(frozen=True, slots=True)
class CheckedDay:
    """One business day as assessed by the latest check run known at the read time."""

    valid_date: date
    status: Status
    run_id: str
    checked_as_of: datetime


@dataclass(frozen=True, slots=True)
class ValueStatus:
    version_id: int
    maturity: str
    valid_date: date
    status: Status


@dataclass(frozen=True, slots=True)
class QualityCheck:
    run_id: str
    curve_id: str
    valid_from: date
    valid_to: date
    checked_as_of: datetime
    rule_set_version: str
    days: tuple[DayStatus, ...]
    values: tuple[ValueStatus, ...]
    findings: tuple[Finding, ...]


def assess(
    *,
    run_id: str,
    curve_id: str,
    valid_from: date,
    valid_to: date,
    checked_as_of: datetime,
    grid: Sequence[str],
    series: Mapping[str, Sequence[Value]],
    thresholds: PlausibilityThresholds,
) -> QualityCheck:
    """Run all rules on one chunk; every in-range value and business day gets a status."""
    business_days = target_business_days(valid_from, valid_to)
    in_range: list[Value] = []
    for maturity in grid:
        for point in series.get(maturity, ()):
            if valid_from <= point.valid_date <= valid_to:
                in_range.append(point)

    findings: list[Finding] = []
    findings.extend(check_range(in_range, thresholds))
    findings.extend(check_completeness(in_range, grid, business_days))
    for maturity in grid:
        findings.extend(check_jumps(series.get(maturity, ()), valid_from, thresholds))

    by_value: dict[tuple[int, str, date], list[Finding]] = defaultdict(list)
    by_day: dict[date, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_day[finding.valid_date].append(finding)
        if finding.version_id is not None and finding.maturity is not None:
            by_value[(finding.version_id, finding.maturity, finding.valid_date)].append(finding)

    values = tuple(
        ValueStatus(
            version_id=point.version_id,
            maturity=point.maturity,
            valid_date=point.valid_date,
            status=worst(by_value.get((point.version_id, point.maturity, point.valid_date), ())),
        )
        for point in in_range
    )
    days = tuple(
        DayStatus(valid_date=day, status=worst(by_day.get(day, ()))) for day in business_days
    )

    return QualityCheck(
        run_id=run_id,
        curve_id=curve_id,
        valid_from=valid_from,
        valid_to=valid_to,
        checked_as_of=checked_as_of,
        rule_set_version=RULE_SET_VERSION,
        days=days,
        values=values,
        findings=tuple(findings),
    )
