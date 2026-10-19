"""Raw delivery store: calls the ``ING`` PL/SQL interface through python-oracledb (thin mode).

Ingestion only calls the ``ing_delivery`` package, as the runtime user that has
``EXECUTE`` on it and nothing else (``docs/project/00-data-ingestion/04-raw-deliveries.md``).
Each delivery is committed on its own, before it is parsed: an answer that fails
validation later is kept for diagnosis and replay.
"""

import hashlib
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

import oracledb

from ingestion.config import DatabaseSettings
from ingestion.domain.delivery import RawDelivery


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
        if self._connection is None:
            raise RuntimeError("OracleDeliveryStore is used outside its context")
        connection = self._connection
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


def _as_utc(moment: datetime | None) -> datetime | None:
    """ING stores times as plain TIMESTAMPs in UTC."""
    return moment.astimezone(UTC).replace(tzinfo=None) if moment is not None else None
