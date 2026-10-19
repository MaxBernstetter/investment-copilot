"""Use case: rebuild published values from stored raw deliveries, without the source."""

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ingestion.application.load_published_curve import ObservationStore, RecordedBatch
from ingestion.domain.delivery import RawDelivery, StoredDelivery
from ingestion.domain.observation import PublishedObservation

Parse = Callable[[RawDelivery], Sequence[PublishedObservation]]
"""The source's parser: validates a payload and maps it (no payload: no values)."""


class StoredDeliveries(Protocol):
    """Port: reads raw deliveries back from ``ING``."""

    def stored(
        self, source_id: str, fetched_from: date, fetched_to: date
    ) -> AsyncIterator[StoredDelivery]:
        """The source's deliveries fetched on these days (UTC, inclusive), in fetch order."""
        ...


@dataclass(frozen=True, slots=True)
class ReplayedDelivery:
    delivery_id: str
    delivered_count: int
    """Observations parsed from the stored payload."""
    batches: tuple[RecordedBatch, ...]


@dataclass(frozen=True, slots=True)
class ReplayResult:
    run_id: str
    deliveries: tuple[ReplayedDelivery, ...]

    @property
    def delivered_count(self) -> int:
        return sum(delivery.delivered_count for delivery in self.deliveries)

    @property
    def recorded_count(self) -> int:
        return sum(b.recorded_count for d in self.deliveries for b in d.batches)

    @property
    def unchanged_count(self) -> int:
        return sum(b.unchanged_count for d in self.deliveries for b in d.batches)


class ReplayDeliveries:
    """Parse each stored delivery of a source again and record its values.

    Deliveries are replayed in the order they were fetched, so a later answer wins over
    an earlier one, as in the original loads. Every value names the delivery it came
    from. The source is never called: there is no source client in this use case.
    Values that persistence already holds are no-ops; a changed parse (a new
    normalization version) or a changed value becomes a new version.
    """

    def __init__(
        self, source_id: str, parse: Parse, deliveries: StoredDeliveries, store: ObservationStore
    ) -> None:
        self._source_id = source_id
        self._parse = parse
        self._deliveries = deliveries
        self._store = store

    async def __call__(self, fetched_from: date, fetched_to: date, run_id: str) -> ReplayResult:
        replayed = [
            await self._replay(stored, run_id)
            async for stored in self._deliveries.stored(self._source_id, fetched_from, fetched_to)
        ]
        return ReplayResult(run_id, tuple(replayed))

    async def _replay(self, stored: StoredDelivery, run_id: str) -> ReplayedDelivery:
        observations = self._parse(stored.delivery)
        batches: list[RecordedBatch] = []
        if observations:
            batches = await self._store.record(
                self._source_id, observations, run_id, stored.delivery_id
            )
        return ReplayedDelivery(stored.delivery_id, len(observations), tuple(batches))
