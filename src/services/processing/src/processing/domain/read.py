"""Read-side quality results: range limits, errors and rule outcome assembly."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from processing.domain.quality import Finding, Rule, Status, worst

MAX_DAYS_RANGE = timedelta(days=366)
"""Largest valid-date span for a quality-per-day read."""

MAX_VALUES_RANGE = timedelta(days=3660)
"""Largest valid-date span for a value-quality read."""

ALL_RULES: tuple[Rule, ...] = tuple(Rule)


class InvalidRangeError(Exception):
    """The requested valid-date range or knowledge-time window is invalid."""


class FutureAsOfError(Exception):
    """The requested knowledge time lies after the database clock."""


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    rule: Rule
    outcome: Status
    finding_count: int


@dataclass(frozen=True, slots=True)
class QualityDayResult:
    valid_date: date
    status: Status
    run_id: str | None
    checked_as_of: datetime | None
    rules: tuple[RuleOutcome, ...]
    findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class QualityDays:
    curve_id: str
    valid_from: date
    valid_to: date
    as_of: datetime
    days: tuple[QualityDayResult, ...]


@dataclass(frozen=True, slots=True)
class ValueQualityResult:
    version_id: int
    maturity: str
    valid_date: date
    status: Status
    flags: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class CurveValueQualities:
    curve_id: str
    valid_from: date
    valid_to: date
    as_of: datetime
    values: tuple[ValueQualityResult, ...]


def rule_outcomes(findings: Sequence[Finding], checked: bool) -> tuple[RuleOutcome, ...]:
    """One outcome per rule for a day or value."""
    if not checked:
        return tuple(RuleOutcome(rule, Status.UNCHECKED, 0) for rule in ALL_RULES)
    return tuple(_rule_outcome(rule, findings) for rule in ALL_RULES)


def unchecked_day(valid_date: date) -> QualityDayResult:
    return QualityDayResult(
        valid_date=valid_date,
        status=Status.UNCHECKED,
        run_id=None,
        checked_as_of=None,
        rules=rule_outcomes((), checked=False),
        findings=(),
    )


def checked_day(
    valid_date: date,
    status: Status,
    run_id: str,
    checked_as_of: datetime,
    findings: Sequence[Finding],
) -> QualityDayResult:
    return QualityDayResult(
        valid_date=valid_date,
        status=status,
        run_id=run_id,
        checked_as_of=checked_as_of,
        rules=rule_outcomes(findings, checked=True),
        findings=tuple(findings),
    )


def _rule_outcome(rule: Rule, findings: Sequence[Finding]) -> RuleOutcome:
    rule_findings = [finding for finding in findings if finding.rule == rule]
    if not rule_findings:
        return RuleOutcome(rule, Status.PASSED, 0)
    return RuleOutcome(rule, worst(rule_findings), len(rule_findings))
