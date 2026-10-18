"""The spool against a real Garage node, opened from settings like the job opens it."""

from datetime import date
from decimal import Decimal

import pytest

from ingestion.config import SpoolSettings
from ingestion.domain.observation import Delivery, PublishedObservation
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.spool import open_spool

pytestmark = pytest.mark.anyio


def delivery(day: date, value: str) -> Delivery:
    return Delivery(
        source_id="ecb",
        window=DateWindow(day, day),
        observations=(PublishedObservation("ecb-aaa-spot", "10Y", day, Decimal(value)),),
        last_modified=None,
    )


async def test_items_are_kept_listed_in_order_removed_and_rejected(
    garage: SpoolSettings,
) -> None:
    spool = open_spool(garage, "ecb")
    first = await spool.put(delivery(date(2026, 10, 15), "2.1230"), "run-1")
    second = await spool.put(delivery(date(2026, 10, 16), "2.2"), "run-2")
    third = await spool.put(delivery(date(2026, 10, 14), "2.0"), "run-3")

    assert await spool.pending() == [first, second, third]

    await spool.remove(first)
    await spool.reject(second)

    assert await spool.pending() == [third]
    await spool.remove(third)
    assert await spool.pending() == []
