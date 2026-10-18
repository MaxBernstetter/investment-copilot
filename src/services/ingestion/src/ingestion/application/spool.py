"""Port: keeps fetched deliveries while persistence is unavailable, until they are recorded."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ingestion.domain.observation import Delivery


@dataclass(frozen=True, slots=True)
class SpooledDelivery:
    """A delivery waiting in the spool, with the run that fetched it."""

    key: str
    """Identifies the item in the spool; items sort by it in fetch order."""
    delivery: Delivery
    run_id: str
    fetched_at: datetime


class DeliverySpool(Protocol):
    """Port: a first-in, first-out store of deliveries that could not be recorded yet."""

    async def put(self, delivery: Delivery, run_id: str) -> SpooledDelivery: ...

    async def pending(self) -> list[SpooledDelivery]:
        """The waiting items, oldest fetch first."""
        ...

    async def remove(self, item: SpooledDelivery) -> None:
        """Drop an item once persistence has recorded it."""
        ...

    async def reject(self, item: SpooledDelivery) -> None:
        """Set aside an item persistence refused, kept for inspection."""
        ...
