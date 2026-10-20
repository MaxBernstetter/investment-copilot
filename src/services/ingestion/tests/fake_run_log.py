from dataclasses import dataclass, field

from ingestion.domain.run import Operation, RunOutcome


@dataclass
class RecordedAttempt:
    run_id: str
    attempt: int
    operation: Operation
    outcome: RunOutcome | None = None


@dataclass
class FakeRunLog:
    attempts: list[RecordedAttempt] = field(default_factory=list)

    async def start(self, run_id: str, operation: Operation) -> int:
        attempt = sum(1 for recorded in self.attempts if recorded.run_id == run_id) + 1
        self.attempts.append(RecordedAttempt(run_id, attempt, operation))
        return attempt

    async def finish(self, run_id: str, attempt: int, outcome: RunOutcome) -> None:
        for recorded in self.attempts:
            if (
                recorded.run_id == run_id
                and recorded.attempt == attempt
                and recorded.outcome is None
            ):
                recorded.outcome = outcome
                return
