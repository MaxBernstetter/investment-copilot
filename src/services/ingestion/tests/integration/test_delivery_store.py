"""OracleDeliveryStore against the ING schema in Oracle Free, as the runtime user."""

import dataclasses
import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest

from ingestion.config import DatabaseSettings
from ingestion.domain.delivery import RawDelivery, StoredDelivery
from ingestion.infrastructure.ing import CorruptDeliveryError, OracleDeliveryStore
from tests.integration.conftest import APP_PASSWORD, OracleDatabase
from tests.recorded import DAILY, payload

pytestmark = pytest.mark.anyio

URL = "https://data-api.ecb.europa.eu/service/data/YC/x?startPeriod=2026-10-01"
CEST = timezone(timedelta(hours=2))


def delivery(content: bytes | None, status: int = 200, etag: str | None = None) -> RawDelivery:
    return RawDelivery(
        source_id="ecb",
        request_url=URL,
        response_status=status,
        fetched_at=datetime(2026, 10, 18, 11, 30, 0, 123456, tzinfo=CEST),
        last_modified=datetime(2026, 10, 16, 10, 0, tzinfo=UTC),
        etag=etag,
        payload=content,
    )


def settings(oracle: OracleDatabase) -> DatabaseSettings:
    return DatabaseSettings.model_validate({"dsn": oracle.dsn, "password": APP_PASSWORD})


async def store(oracle: OracleDatabase, raw: RawDelivery) -> str:
    async with OracleDeliveryStore(settings(oracle)) as deliveries:
        return await deliveries.store(raw, "it-run")


async def read_back(oracle: OracleDatabase, source_id: str, day: date) -> list[StoredDelivery]:
    async with OracleDeliveryStore(settings(oracle)) as deliveries:
        return [stored async for stored in deliveries.stored(source_id, day, day)]


def stored(oracle: OracleDatabase, delivery_id: str) -> dict[str, Any]:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select * from delivery where delivery_id = :id", id=int(delivery_id))
        columns = [column.name.lower() for column in cursor.description]
        row = cursor.fetchone()
        assert row is not None
        values = dict(zip(columns, row, strict=True))
        if values["payload"] is not None:
            values["payload"] = values["payload"].read()
        return values


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(payload(DAILY), id="recorded ECB payload"),
        pytest.param(bytes(range(256)) * 400, id="100 KB of every byte value"),
    ],
)
async def test_stores_the_payload_byte_for_byte_with_its_metadata(
    oracle: OracleDatabase, content: bytes
) -> None:
    row = stored(oracle, await store(oracle, delivery(content, etag='"v7"')))

    assert row["payload"] == content
    assert row["payload_sha256"] == hashlib.sha256(content).hexdigest()
    assert {key: row[key] for key in ("source_id", "run_id", "request_url", "etag")} == {
        "source_id": "ecb",
        "run_id": "it-run",
        "request_url": URL,
        "etag": '"v7"',
    }
    assert row["response_status"] == 200
    assert row["fetched_at"] == datetime(2026, 10, 18, 9, 30, 0, 123456)  # UTC
    assert row["last_modified"] == datetime(2026, 10, 16, 10, 0)


async def test_stores_an_empty_delivery_without_payload(oracle: OracleDatabase) -> None:
    row = stored(oracle, await store(oracle, delivery(None, status=404)))

    assert (row["response_status"], row["payload"], row["payload_sha256"]) == (404, None, None)


async def test_every_delivery_gets_its_own_id(oracle: OracleDatabase) -> None:
    first = await store(oracle, delivery(None, status=304))
    second = await store(oracle, delivery(None, status=304))

    assert first != second


async def test_reads_the_deliveries_of_a_fetch_day_back_as_stored(
    oracle: OracleDatabase,
) -> None:
    later = dataclasses.replace(
        delivery(payload(DAILY), etag='"v7"'),
        source_id="it-read",
        fetched_at=datetime(2026, 10, 18, 23, 59, tzinfo=UTC),
    )
    earlier = dataclasses.replace(delivery(None, status=404), source_id="it-read")
    next_day = dataclasses.replace(earlier, fetched_at=datetime(2026, 10, 19, 0, 0, tzinfo=UTC))
    ids = [await store(oracle, raw) for raw in (later, earlier, next_day)]

    replayed = await read_back(oracle, "it-read", date(2026, 10, 18))

    assert replayed == [
        StoredDelivery(
            ids[1], dataclasses.replace(earlier, fetched_at=earlier.fetched_at.astimezone(UTC))
        ),
        StoredDelivery(ids[0], later),
    ]


async def test_a_payload_that_no_longer_matches_its_hash_is_not_replayed(
    oracle: OracleDatabase,
) -> None:
    delivery_id = await store(
        oracle, dataclasses.replace(delivery(b"1,2,3"), source_id="it-corrupt")
    )
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "update delivery set payload = utl_raw.cast_to_raw('1,2,4') where delivery_id = :id",
            id=int(delivery_id),
        )
        connection.commit()

    with pytest.raises(CorruptDeliveryError, match=delivery_id):
        await read_back(oracle, "it-corrupt", date(2026, 10, 18))
