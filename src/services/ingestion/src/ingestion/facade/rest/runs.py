"""Maps run attempts to the transparency ``Run`` shape of the contracts."""

from contracts.transparency.v1 import Run

from ingestion.domain.run import RunAttempt

SERVICE = "ingestion"


def to_run(attempt: RunAttempt) -> Run:
    finished = attempt.finished_at
    duration = None if finished is None else (finished - attempt.started_at).total_seconds()
    return Run(
        run_id=attempt.run_id,
        attempt=attempt.attempt,
        service=SERVICE,
        operation=attempt.operation.value,
        status=attempt.status.value,
        started_at=attempt.started_at,
        finished_at=finished,
        duration_seconds=duration,
        delivered_count=attempt.counts.delivered_count,
        recorded_count=attempt.counts.recorded_count,
        unchanged_count=attempt.counts.unchanged_count,
        error_type=attempt.error_type,
        error_message=attempt.error_message,
    )
