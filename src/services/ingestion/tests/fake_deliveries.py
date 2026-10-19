"""An in-memory stand-in for the raw delivery store (``ING``)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date

from ingestion.domain.delivery import RawDelivery, StoredDelivery


@dataclass
class FakeDeliveryStore:
    """Keeps each stored delivery with its run id; delivery ids count up from 1."""

    stored_with_run: list[tuple[RawDelivery, str]] = field(default_factory=list)

    async def store(self, delivery: RawDelivery, run_id: str) -> str:
        self.stored_with_run.append((delivery, run_id))
        return str(len(self.stored_with_run))

    async def stored(
        self, source_id: str, fetched_from: date, fetched_to: date
    ) -> AsyncIterator[StoredDelivery]:
        for number, (delivery, _) in enumerate(self.stored_with_run, start=1):
            fetched_on = delivery.fetched_at.date()
            if delivery.source_id == source_id and fetched_from <= fetched_on <= fetched_to:
                yield StoredDelivery(str(number), delivery)

    @property
    def deliveries(self) -> list[RawDelivery]:
        return [delivery for delivery, _ in self.stored_with_run]
