"""Run attempt outcomes for ingestion jobs."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Operation(StrEnum):
    DAILY = "daily"
    HISTORY = "history"
    REPLAY = "replay"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RunCounts:
    delivered_count: int = 0
    recorded_count: int = 0
    unchanged_count: int = 0


@dataclass(frozen=True, slots=True)
class RunAttempt:
    """One stored attempt of a run, as read back from the run history (UTC times)."""

    attempt_id: int
    run_id: str
    attempt: int
    operation: Operation
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    counts: RunCounts
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: RunStatus
    counts: RunCounts
    error_type: str | None = None
    error_message: str | None = None


def outcome_of(counts: RunCounts, committed_steps: int, error: Exception | None) -> RunOutcome:
    """Map counts and failure to a finished status.

    No error → succeeded. An error after at least one committed step → partial.
    An error before any step → failed.
    """
    if error is None:
        return RunOutcome(RunStatus.SUCCEEDED, counts)
    if committed_steps > 0:
        return RunOutcome(
            RunStatus.PARTIAL,
            counts,
            type(error).__name__,
            str(error),
        )
    return RunOutcome(
        RunStatus.FAILED,
        counts,
        type(error).__name__,
        str(error),
    )
