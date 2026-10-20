"""Use case: load a published curve from its source into the bitemporal core."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ingestion.domain.delivery import RawDelivery
from ingestion.domain.observation import PublishedObservation
from ingestion.domain.windows import DateWindow


class CurveSource(Protocol):
    """Port: a source of a published curve.

    Fetching and parsing are separate steps, so every answer is stored before it is
    parsed, and replay can parse a stored answer without calling the source.
    """

    async def fetch(self, window: DateWindow) -> RawDelivery: ...

    def parse(self, delivery: RawDelivery) -> Sequence[PublishedObservation]:
        """Validate the payload against the declared schema and map it (empty: none)."""
        ...


class DeliveryStore(Protocol):
    """Port: keeps raw deliveries (ingestion's ``ING`` schema)."""

    async def store(self, delivery: RawDelivery, run_id: str) -> str:
        """Store the delivery durably and return its delivery id."""
        ...


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
        self,
        source_id: str,
        observations: Sequence[PublishedObservation],
        run_id: str,
        delivery_id: str,
    ) -> list[RecordedBatch]: ...


@dataclass(frozen=True, slots=True)
class WindowResult:
    window: DateWindow
    delivery_id: str
    """The raw delivery the window's values came from."""
    delivered_count: int
    """Observations the source delivered for the window."""
    batches: tuple[RecordedBatch, ...]
    last_modified: datetime | None
    """Delivery metadata from the source; not a knowledge time."""

    @property
    def recorded_count(self) -> int:
        return sum(batch.recorded_count for batch in self.batches)

    @property
    def unchanged_count(self) -> int:
        return sum(batch.unchanged_count for batch in self.batches)


@dataclass(frozen=True, slots=True)
class LoadResult:
    run_id: str
    attempt: int
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

    Yields one ``WindowResult`` per window after it is stored and recorded. Windows run
    one after another (the source access policy allows no fan-out). Each answer is stored
    as a raw delivery before it is parsed, and every value recorded from it names that
    delivery. A window without data is a successful step with zero rows (its empty
    delivery is stored too). An invalid payload or a failed write stops the load;
    deliveries and windows stored before it stay stored, the invalid payload included.
    """

    def __init__(
        self, source: CurveSource, deliveries: DeliveryStore, store: ObservationStore
    ) -> None:
        self._source = source
        self._deliveries = deliveries
        self._store = store

    async def __call__(
        self, windows: Sequence[DateWindow], run_id: str
    ) -> AsyncIterator[WindowResult]:
        for window in windows:
            yield await self._load(window, run_id)

    async def _load(self, window: DateWindow, run_id: str) -> WindowResult:
        delivery = await self._source.fetch(window)
        delivery_id = await self._deliveries.store(delivery, run_id)
        observations = self._source.parse(delivery)
        batches: list[RecordedBatch] = []
        if observations:
            batches = await self._store.record(
                delivery.source_id, observations, run_id, delivery_id
            )
        return WindowResult(
            window, delivery_id, len(observations), tuple(batches), delivery.last_modified
        )
