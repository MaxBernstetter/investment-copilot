"""Raw delivery store: calls the ``ING`` PL/SQL interface through python-oracledb (thin mode).

Ingestion only calls the ``ing_delivery`` package, as the runtime user that has
``EXECUTE`` on it and nothing else (``docs/project/00-data-ingestion/04-raw-deliveries.md``).
Each delivery is committed on its own, before it is parsed: an answer that fails
validation later is kept for diagnosis and replay.
"""

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta
from types import TracebackType
from typing import Self

import oracledb

from ingestion.config import DatabaseSettings
from ingestion.domain.delivery import RawDelivery, StoredDelivery


class CorruptDeliveryError(Exception):
    """A stored payload no longer matches its hash; it is not replayed."""


class OracleDeliveryStore:
    """One connection per job run. Use as an async context manager."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._connection: oracledb.AsyncConnection | None = None

    async def __aenter__(self) -> Self:
        self._connection = await oracledb.connect_async(
            dsn=self._settings.dsn,
            user=self._settings.user,
            password=self._settings.password.get_secret_value(),
        )
        self._connection.call_timeout = self._settings.call_timeout_ms
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def store(self, delivery: RawDelivery, run_id: str) -> str:
        connection = self._connected()
        cursor = connection.cursor()
        # Typed binds: a null must still bind as BLOB, a payload may exceed the 32 KB
        # limit of a PL/SQL RAW (so it goes in as a LOB), and a datetime would otherwise
        # bind as DATE and lose its fractional seconds.
        payload = cursor.var(oracledb.DB_TYPE_BLOB)
        payload_sha256 = None
        if delivery.payload is not None:
            payload.setvalue(0, await connection.createlob(oracledb.DB_TYPE_BLOB, delivery.payload))
            payload_sha256 = hashlib.sha256(delivery.payload).hexdigest()
        fetched_at = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
        fetched_at.setvalue(0, _as_utc(delivery.fetched_at))
        last_modified = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
        last_modified.setvalue(0, _as_utc(delivery.last_modified))
        delivery_id = await cursor.callfunc(
            "ing.ing_delivery.record_delivery",
            int,
            keyword_parameters={
                "p_source_id": delivery.source_id,
                "p_run_id": run_id,
                "p_request_url": delivery.request_url,
                "p_response_status": delivery.response_status,
                "p_fetched_at": fetched_at,
                "p_last_modified": last_modified,
                "p_etag": delivery.etag,
                "p_payload": payload,
                "p_payload_sha256": payload_sha256,
            },
        )
        await connection.commit()
        return str(delivery_id)

    async def stored(
        self, source_id: str, fetched_from: date, fetched_to: date
    ) -> AsyncIterator[StoredDelivery]:
        """Streams the deliveries one at a time, so memory stays bounded by one payload.

        Raises ``CorruptDeliveryError`` when a payload does not match its stored hash.
        """
        cursor = self._connected().cursor()
        rows = await cursor.callfunc(
            "ing.ing_delivery.get_deliveries",
            oracledb.DB_TYPE_CURSOR,
            [
                source_id,
                datetime.combine(fetched_from, time()),
                datetime.combine(fetched_to + timedelta(days=1), time()),
            ],
        )
        async for row in rows:
            yield await _stored_delivery(*row)

    def _connected(self) -> oracledb.AsyncConnection:
        if self._connection is None:
            raise RuntimeError("OracleDeliveryStore is used outside its context")
        return self._connection


async def _stored_delivery(
    delivery_id: int,
    source_id: str,
    _run_id: str,
    request_url: str,
    response_status: int,
    fetched_at: datetime,
    last_modified: datetime | None,
    etag: str | None,
    payload_lob: oracledb.AsyncLOB | None,
    payload_sha256: str | None,
) -> StoredDelivery:
    payload: bytes | None = None
    if payload_lob is not None:
        payload = await payload_lob.read()
        if hashlib.sha256(payload).hexdigest() != payload_sha256:
            raise CorruptDeliveryError(f"delivery {delivery_id}: payload does not match its hash")
    delivery = RawDelivery(
        source_id=source_id,
        request_url=request_url,
        response_status=response_status,
        fetched_at=fetched_at.replace(tzinfo=UTC),
        last_modified=last_modified.replace(tzinfo=UTC) if last_modified else None,
        etag=etag,
        payload=payload,
    )
    return StoredDelivery(str(delivery_id), delivery)


def _as_utc(moment: datetime | None) -> datetime | None:
    """ING stores times as plain TIMESTAMPs in UTC."""
    return moment.astimezone(UTC).replace(tzinfo=None) if moment is not None else None
