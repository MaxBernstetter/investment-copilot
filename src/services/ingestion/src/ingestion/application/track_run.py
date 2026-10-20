"""Use case: record each job run as a started attempt and a finished outcome."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from ingestion.domain.run import Operation, RunCounts, RunOutcome, outcome_of


class Step(Protocol):
    @property
    def delivered_count(self) -> int: ...

    @property
    def recorded_count(self) -> int: ...

    @property
    def unchanged_count(self) -> int: ...


class RunLog(Protocol):
    async def start(self, run_id: str, operation: Operation) -> int:
        """Records a new running attempt; returns its number."""
        ...

    async def finish(self, run_id: str, attempt: int, outcome: RunOutcome) -> None: ...


@dataclass(frozen=True, slots=True)
class TrackedRun[S: Step]:
    attempt: int
    steps: tuple[S, ...]


def _sum_counts(steps: Sequence[Step]) -> RunCounts:
    return RunCounts(
        delivered_count=sum(step.delivered_count for step in steps),
        recorded_count=sum(step.recorded_count for step in steps),
        unchanged_count=sum(step.unchanged_count for step in steps),
    )


class TrackRun:
    def __init__(self, run_log: RunLog) -> None:
        self._run_log = run_log

    async def __call__[S: Step](
        self, run_id: str, operation: Operation, steps: AsyncIterator[S]
    ) -> TrackedRun[S]:
        attempt = await self._run_log.start(run_id, operation)
        done: list[S] = []
        try:
            async for step in steps:
                done.append(step)
        except Exception as error:
            try:
                await self._run_log.finish(
                    run_id, attempt, outcome_of(_sum_counts(done), len(done), error)
                )
            except Exception as finish_error:
                error.add_note(f"run log finish failed: {finish_error!r}")
            raise
        await self._run_log.finish(run_id, attempt, outcome_of(_sum_counts(done), len(done), None))
        return TrackedRun(attempt, tuple(done))
