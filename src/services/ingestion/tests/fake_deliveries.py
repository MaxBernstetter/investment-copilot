"""An in-memory stand-in for the raw delivery store (``ING``)."""

from dataclasses import dataclass, field

from ingestion.domain.delivery import RawDelivery


@dataclass
class FakeDeliveryStore:
    """Keeps each stored delivery with its run id; delivery ids count up from 1."""

    stored: list[tuple[RawDelivery, str]] = field(default_factory=list)

    async def store(self, delivery: RawDelivery, run_id: str) -> str:
        self.stored.append((delivery, run_id))
        return str(len(self.stored))

    @property
    def deliveries(self) -> list[RawDelivery]:
        return [delivery for delivery, _ in self.stored]
