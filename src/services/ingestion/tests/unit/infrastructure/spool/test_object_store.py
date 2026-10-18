"""ObjectStoreSpool on an in-memory and a local-directory store. No network."""

import io
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import obstore
import polars as pl
import pytest
from obstore.store import LocalStore, MemoryStore, ObjectStore
from pydantic import ValidationError

from ingestion.config import SpoolSettings
from ingestion.domain.observation import Delivery, PublishedObservation
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.spool import ObjectStoreSpool, open_spool

pytestmark = pytest.mark.anyio

FIRST_FETCH = datetime(2026, 10, 18, 13, 15, tzinfo=UTC)
LAST_MODIFIED = datetime(2026, 10, 16, 14, 2, 11, tzinfo=UTC)


class Clock:
    """Each call is one second after the previous one, starting at ``FIRST_FETCH``."""

    def __init__(self) -> None:
        self._ticks: Iterator[int] = iter(range(1_000))

    def __call__(self) -> datetime:
        return FIRST_FETCH + timedelta(seconds=next(self._ticks))


@pytest.fixture(params=["memory", "local"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> ObjectStore:
    return MemoryStore() if request.param == "memory" else LocalStore(tmp_path)


@pytest.fixture
def spool(store: ObjectStore) -> ObjectStoreSpool:
    return ObjectStoreSpool(store, "ecb", now=Clock())


def delivery(start: date, *values: str, last_modified: datetime | None = LAST_MODIFIED) -> Delivery:
    return Delivery(
        source_id="ecb",
        window=DateWindow(start, start + timedelta(days=4)),
        observations=tuple(
            PublishedObservation("ecb-aaa-spot", f"{i + 1}Y", start, Decimal(value))
            for i, value in enumerate(values)
        ),
        last_modified=last_modified,
    )


def paths(store: ObjectStore, prefix: str) -> list[str]:
    return sorted(meta["path"] for meta in obstore.list(store, prefix=prefix).collect())


async def test_an_empty_spool_has_nothing_pending(spool: ObjectStoreSpool) -> None:
    assert await spool.pending() == []


async def test_a_spooled_delivery_comes_back_unchanged_with_its_run(
    spool: ObjectStoreSpool,
) -> None:
    put = await spool.put(delivery(date(2026, 10, 12), "2.1230", "-0.004917", "3"), "run-1")

    [pending] = await spool.pending()

    assert pending == put
    assert pending.run_id == "run-1"
    assert pending.fetched_at == FIRST_FETCH
    assert pending.delivery == delivery(date(2026, 10, 12), "2.1230", "-0.004917", "3")


async def test_the_published_digits_are_kept_exactly(spool: ObjectStoreSpool) -> None:
    await spool.put(delivery(date(2026, 10, 12), "2.1230", "1E-7"), "run-1")

    [pending] = await spool.pending()

    assert [str(o.value) for o in pending.delivery.observations] == ["2.1230", "1E-7"]


async def test_a_window_without_observations_keeps_its_metadata(spool: ObjectStoreSpool) -> None:
    await spool.put(delivery(date(2026, 10, 10), last_modified=None), "run-1")

    [pending] = await spool.pending()

    assert pending.delivery == delivery(date(2026, 10, 10), last_modified=None)


async def test_pending_items_come_in_fetch_order_not_window_order(
    spool: ObjectStoreSpool,
) -> None:
    later_window = await spool.put(delivery(date(2026, 10, 12), "1"), "run-1")
    earlier_window = await spool.put(delivery(date(2025, 1, 6), "2"), "run-2")

    assert await spool.pending() == [later_window, earlier_window]


async def test_a_removed_item_is_no_longer_pending(
    spool: ObjectStoreSpool, store: ObjectStore
) -> None:
    first = await spool.put(delivery(date(2026, 10, 5), "1"), "run-1")
    second = await spool.put(delivery(date(2026, 10, 12), "2"), "run-1")

    await spool.remove(first)

    assert await spool.pending() == [second]
    assert paths(store, "ecb/") == [second.key]


async def test_a_rejected_item_is_set_aside_for_inspection(
    spool: ObjectStoreSpool, store: ObjectStore
) -> None:
    item = await spool.put(delivery(date(2026, 10, 12), "1"), "run-1")

    await spool.reject(item)

    assert await spool.pending() == []
    assert paths(store, "ecb/") == [
        "ecb/rejected/20261018T131500000000Z_2026-10-12_2026-10-16.parquet"
    ]


async def test_each_source_has_its_own_spool(store: ObjectStore) -> None:
    await ObjectStoreSpool(store, "other", now=Clock()).put(delivery(date(2026, 10, 12)), "r")

    assert await ObjectStoreSpool(store, "ecb", now=Clock()).pending() == []


async def test_an_object_of_another_spool_format_is_refused(
    spool: ObjectStoreSpool, store: ObjectStore
) -> None:
    buffer = io.BytesIO()
    pl.DataFrame({"value": ["1"]}).write_parquet(buffer, metadata={"spool_format": "2"})
    await obstore.put_async(
        store, "ecb/pending/20261018T000000000000Z_x_y.parquet", buffer.getvalue()
    )

    with pytest.raises(ValueError, match="unknown spool format '2'"):
        await spool.pending()


def spool_settings(url: str) -> SpoolSettings:
    return SpoolSettings.model_validate(
        {
            "url": url,
            "endpoint": "http://localhost:3900",
            "access_key_id": "GK0123",
            "secret_access_key": "secret",
        }
    )


def test_the_spool_is_opened_on_the_configured_bucket() -> None:
    assert isinstance(open_spool(spool_settings("s3://ingestion-spool"), "ecb"), ObjectStoreSpool)


@pytest.mark.parametrize("url", ["http://ingestion-spool", "s3://bucket/prefix", "s3://"])
def test_a_spool_url_must_name_a_bucket_only(url: str) -> None:
    with pytest.raises(ValidationError):
        spool_settings(url)
