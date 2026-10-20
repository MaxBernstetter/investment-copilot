"""Quality vocabulary: rules, severities, statuses, values and findings."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Rule(StrEnum):
    RANGE = "range"
    JUMP = "jump"
    MISSING_DATE = "missing-date"
    MISSING_MATURITY = "missing-maturity"


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"


class Status(StrEnum):
    PASSED = "passed"
    INFO = "info"
    WARN = "warn"
    UNCHECKED = "unchecked"


@dataclass(frozen=True, slots=True)
class Value:
    """One published value of a maturity on a valid date, as persisted in one version."""

    version_id: int
    maturity: str
    valid_date: date
    value: Decimal


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule hit. Maturity, version and value are empty for day-level rules."""

    rule: Rule
    severity: Severity
    valid_date: date
    maturity: str | None
    version_id: int | None
    value: Decimal | None
    explanation: str
    evidence: str


def worst(findings: Iterable[Finding]) -> Status:
    """Warn beats info beats passed."""
    severities = {finding.severity for finding in findings}
    if Severity.WARN in severities:
        return Status.WARN
    if Severity.INFO in severities:
        return Status.INFO
    return Status.PASSED
