"""The outcome of a quality check started on demand."""

from dataclasses import dataclass
from datetime import datetime


class QualityChecksDisabledError(Exception):
    """This deployment does not let consumers start quality checks."""


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    curve_id: str
    run_id: str
    checked_as_of: datetime | None
    days: int
    values: int
    warn_count: int
    info_count: int
