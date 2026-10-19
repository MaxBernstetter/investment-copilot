"""OracleDeliveryStore against the ING schema in Oracle Free, as the runtime user."""

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from ingestion.config import DatabaseSettings
from ingestion.domain.delivery import RawDelivery
from ingestion.infrastructure.ing import OracleDeliveryStore
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


async def store(oracle: OracleDatabase, raw: RawDelivery) -> str:
    settings = DatabaseSettings.model_validate({"dsn": oracle.dsn, "password": APP_PASSWORD})
    async with OracleDeliveryStore(settings) as deliveries:
        return await deliveries.store(raw, "it-run")


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
