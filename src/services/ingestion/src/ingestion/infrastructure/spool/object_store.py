"""The delivery spool on an S3-compatible object store (Garage), as Parquet objects.

One object per delivery. Its rows are the observations, with ``value`` as text so
the published digits come back exactly; the delivery and the run that fetched it are
the file's key-value metadata. Keys sort in fetch order::

    <source>/pending/<fetched_at>_<window start>_<window end>.parquet
    <source>/rejected/...   (refused by persistence, kept for inspection)
"""

import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import obstore
import polars as pl
from obstore.store import ObjectStore, from_url
from opentelemetry import metrics

from ingestion.application.spool import SpooledDelivery
from ingestion.config import SpoolSettings
from ingestion.domain.observation import Delivery, PublishedObservation
from ingestion.domain.windows import DateWindow

SPOOL_FORMAT = "1"
"""Version of the object layout below; bumped on any incompatible change."""
EVENTS_METRIC = "yl_ingestion_spool_events_total"
SCHEMA = {"curve_id": pl.String, "maturity": pl.String, "valid_date": pl.Date, "value": pl.String}


class ObjectStoreSpool:
    """The ``DeliverySpool`` of one source on an object store."""

    def __init__(
        self,
        store: ObjectStore,
        source_id: str,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        meter: metrics.Meter | None = None,
    ) -> None:
        self._store = store
        self._source_id = source_id
        self._pending = f"{source_id}/pending/"
        self._rejected = f"{source_id}/rejected/"
        self._now = now
        self._events = (meter or metrics.get_meter("ingestion")).create_counter(
            EVENTS_METRIC,
            unit="1",
            description="Deliveries spooled, drained (recorded) and rejected, by source",
        )

    async def put(self, delivery: Delivery, run_id: str) -> SpooledDelivery:
        fetched_at = self._now()
        window = delivery.window
        name = f"{fetched_at:%Y%m%dT%H%M%S%fZ}_{window.start}_{window.end}.parquet"
        item = SpooledDelivery(self._pending + name, delivery, run_id, fetched_at)
        await obstore.put_async(self._store, item.key, _encode(item))
        self._count("spooled")
        return item

    async def pending(self) -> list[SpooledDelivery]:
        objects = await obstore.list(self._store, prefix=self._pending).collect_async()
        return [await self._read(path) for path in sorted(meta["path"] for meta in objects)]

    async def remove(self, item: SpooledDelivery) -> None:
        await obstore.delete_async(self._store, item.key)
        self._count("drained")

    async def reject(self, item: SpooledDelivery) -> None:
        target = self._rejected + item.key.removeprefix(self._pending)
        await obstore.rename_async(self._store, item.key, target)
        self._count("rejected")

    def _count(self, event: str) -> None:
        self._events.add(1, {"source": self._source_id, "event": event})

    async def _read(self, path: str) -> SpooledDelivery:
        response = await obstore.get_async(self._store, path)
        return _decode(path, bytes(await response.bytes_async()))


def open_spool(settings: SpoolSettings, source_id: str) -> ObjectStoreSpool:
    """The spool of ``source_id`` in the configured bucket."""
    store = from_url(
        settings.url,
        config={
            "endpoint": str(settings.endpoint),
            "region": settings.region,
            "access_key_id": settings.access_key_id,
            "secret_access_key": settings.secret_access_key.get_secret_value(),
        },
        client_options={"allow_http": settings.endpoint.scheme == "http"},
    )
    return ObjectStoreSpool(store, source_id)


def _encode(item: SpooledDelivery) -> bytes:
    delivery = item.delivery
    frame = pl.DataFrame(
        [(o.curve_id, o.maturity, o.valid_date, str(o.value)) for o in delivery.observations],
        schema=SCHEMA,
        orient="row",
    )
    metadata = {
        "spool_format": SPOOL_FORMAT,
        "source_id": delivery.source_id,
        "run_id": item.run_id,
        "fetched_at": item.fetched_at.isoformat(),
        "window_start": delivery.window.start.isoformat(),
        "window_end": delivery.window.end.isoformat(),
        "last_modified": delivery.last_modified.isoformat() if delivery.last_modified else "",
    }
    buffer = io.BytesIO()
    frame.write_parquet(buffer, metadata=metadata)
    return buffer.getvalue()


def _decode(key: str, content: bytes) -> SpooledDelivery:
    metadata = pl.read_parquet_metadata(io.BytesIO(content))
    if metadata.get("spool_format") != SPOOL_FORMAT:
        raise ValueError(f"{key}: unknown spool format {metadata.get('spool_format')!r}")
    frame = pl.read_parquet(io.BytesIO(content), schema=SCHEMA)
    observations = tuple(
        PublishedObservation(curve_id, maturity, valid_date, Decimal(value))
        for curve_id, maturity, valid_date, value in frame.iter_rows()
    )
    last_modified = metadata["last_modified"]
    delivery = Delivery(
        source_id=metadata["source_id"],
        window=DateWindow(
            date.fromisoformat(metadata["window_start"]),
            date.fromisoformat(metadata["window_end"]),
        ),
        observations=observations,
        last_modified=datetime.fromisoformat(last_modified) if last_modified else None,
    )
    return SpooledDelivery(
        key, delivery, metadata["run_id"], datetime.fromisoformat(metadata["fetched_at"])
    )
