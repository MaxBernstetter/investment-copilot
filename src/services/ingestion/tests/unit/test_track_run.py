"""TrackRun against a fake run log and a failing step iterator. No I/O."""

from collections.abc import AsyncIterator
from typing import Never

import pytest

from ingestion.application.track_run import TrackRun
from ingestion.domain.run import Operation, RunOutcome

pytestmark = pytest.mark.anyio


class FakeRunLog:
    async def start(self, run_id: str, operation: Operation) -> int:
        return 1

    async def finish(self, run_id: str, attempt: int, outcome: RunOutcome) -> None:
        raise RuntimeError("db down")


async def _failing_steps() -> AsyncIterator[Never]:
    raise ValueError("boom")
    yield  # pragma: no cover - makes this an async generator


async def test_keeps_the_load_error_when_finishing_the_run_fails() -> None:
    with pytest.raises(ValueError, match="boom") as raised:
        await TrackRun(FakeRunLog())("run-1", Operation.DAILY, _failing_steps())

    assert any("db down" in note for note in raised.value.__notes__)
