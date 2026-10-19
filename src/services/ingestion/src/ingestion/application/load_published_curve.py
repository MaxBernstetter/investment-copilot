"""Use case: load a published curve from its source into the bitemporal core."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ingestion.domain.observation import Delivery, PublishedObservation
from ingestion.domain.windows import DateWindow


class CurveSource(Protocol):
    """Port: fetches and validates one window of a published curve."""

    async def fetch(self, window: DateWindow) -> Delivery: ...


@dataclass(frozen=True, slots=True)
class RecordedBatch:
    """Persistence's answer to one write: versions stored and their knowledge time."""

    recorded_count: int
    """New versions stored."""
    unchanged_count: int
    """Observations persistence already held with the same value: no new version."""
    known_from: datetime


class ObservationStore(Protocol):
    """Port: records published observations as versions in the bitemporal core."""

    async def record(
        self, source_id: str, observations: Sequence[PublishedObservation], run_id: str
    ) -> list[RecordedBatch]: ...


@dataclass(frozen=True, slots=True)
class WindowResult:
    window: DateWindow
    delivered_count: int
    """Observations the source delivered for the window."""
    batches: tuple[RecordedBatch, ...]
    last_modified: datetime | None
    """Delivery metadata from the source; not a knowledge time."""


@dataclass(frozen=True, slots=True)
class LoadResult:
    run_id: str
    windows: tuple[WindowResult, ...]

    @property
    def delivered_count(self) -> int:
        return sum(window.delivered_count for window in self.windows)

    @property
    def recorded_count(self) -> int:
        return sum(batch.recorded_count for window in self.windows for batch in window.batches)

    @property
    def unchanged_count(self) -> int:
        return sum(batch.unchanged_count for window in self.windows for batch in window.batches)


class LoadPublishedCurve:
    """Fetch each window from the source, in order, and record what it delivered.

    Windows run one after another (the source access policy allows no fan-out). A
    window without data is a successful step with zero rows. An invalid delivery or a
    failed write stops the load; windows recorded before it stay recorded.
    """

    def __init__(self, source: CurveSource, store: ObservationStore) -> None:
        self._source = source
        self._store = store

    async def __call__(self, windows: Sequence[DateWindow], run_id: str) -> LoadResult:
        results = [await self._load(window, run_id) for window in windows]
        return LoadResult(run_id, tuple(results))

    async def _load(self, window: DateWindow, run_id: str) -> WindowResult:
        delivery = await self._source.fetch(window)
        batches: list[RecordedBatch] = []
        if delivery.observations:
            batches = await self._store.record(delivery.source_id, delivery.observations, run_id)
        return WindowResult(
            window, len(delivery.observations), tuple(batches), delivery.last_modified
        )
