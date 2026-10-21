"""A stand-in for the run history reads: records each call and answers with preset attempts."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ingestion.domain.run import RunAttempt


@dataclass
class StubRunHistory:
    """Answers from ``attempts`` (given newest first) and records the keyword arguments."""

    attempts: list[RunAttempt] = field(default_factory=list)
    list_calls: list[dict[str, object]] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)
    alert_calls: list[datetime] = field(default_factory=list)

    async def list_attempts(
        self,
        *,
        started_from: datetime | None,
        started_before: datetime | None,
        before_attempt_id: int | None,
        limit: int,
    ) -> Sequence[RunAttempt]:
        self.list_calls.append(
            {
                "started_from": started_from,
                "started_before": started_before,
                "before_attempt_id": before_attempt_id,
                "limit": limit,
            }
        )
        rows = [
            attempt
            for attempt in self.attempts
            if before_attempt_id is None or attempt.attempt_id < before_attempt_id
        ]
        return rows[:limit]

    async def get_attempts(self, run_id: str) -> Sequence[RunAttempt]:
        self.get_calls.append(run_id)
        return sorted(
            (attempt for attempt in self.attempts if attempt.run_id == run_id),
            key=lambda attempt: attempt.attempt,
        )

    async def alert_attempts(self, *, cleared_after: datetime) -> Sequence[RunAttempt]:
        self.alert_calls.append(cleared_after)
        return self.attempts
