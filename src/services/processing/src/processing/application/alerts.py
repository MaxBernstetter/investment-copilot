"""Business alert conditions of the processing service, evaluated from stored quality results."""

from dataclasses import dataclass
from datetime import datetime

QUALITY_WARN = "quality-warn"


@dataclass(frozen=True, slots=True)
class LatestCheckRun:
    """The most recent check run of one curve, with its number of days in warn."""

    curve_id: str
    recorded_at: datetime
    warn_days: int


def quality_warn_active(run: LatestCheckRun) -> bool:
    """The quality-warn alert is active while the latest check run has a warn day."""
    return run.warn_days > 0
