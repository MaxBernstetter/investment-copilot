"""Per-day quality results as the access service reads them from processing."""

from dataclasses import dataclass
from datetime import date, datetime

from access.domain.quality import QualityStatus, Severity


@dataclass(frozen=True, slots=True)
class QualityFinding:
    rule: str
    severity: Severity
    maturity: str | None
    version_id: int | None
    value: float | None
    explanation: str
    evidence: str


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    rule: str
    outcome: QualityStatus
    finding_count: int


@dataclass(frozen=True, slots=True)
class QualityDay:
    valid_date: date
    status: QualityStatus
    run_id: str | None
    checked_as_of: datetime | None
    rules: tuple[RuleOutcome, ...]
    findings: tuple[QualityFinding, ...]


@dataclass(frozen=True, slots=True)
class QualityDays:
    curve_id: str
    valid_from: date
    valid_to: date
    as_of: datetime
    days: tuple[QualityDay, ...]
