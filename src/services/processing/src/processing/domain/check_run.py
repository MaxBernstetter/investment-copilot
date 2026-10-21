"""A recorded quality check run, numbered as one attempt of its run id."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CheckRunAttempt:
    """One stored check run. ``attempt`` is its 1-based position within ``run_id``."""

    check_run_id: int
    run_id: str
    attempt: int
    recorded_at: datetime
    value_count: int
    """Values the run checked; equal to the run's stored value rows."""
