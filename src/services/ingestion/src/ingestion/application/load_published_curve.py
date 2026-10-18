"""Use case: load a published curve from its source into the bitemporal core."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ingestion.application.spool import DeliverySpool
from ingestion.domain.observation import Delivery, PublishedObservation
from ingestion.domain.windows import DateWindow


class CurveSource(Protocol):
    """Port: fetches and validates one window of a published curve."""

    async def fetch(self, window: DateWindow) -> Delivery: ...


@dataclass(frozen=True, slots=True)
class RecordedBatch:
    """Persistence's answer to one write: versions stored and their knowledge time."""

    recorded_count: int
    """New versions stored."""
    unchanged_count: int
    """Observations persistence already held with the same value: no new version."""
    known_from: datetime


class StoreUnavailableError(Exception):
    """The store could not take the observations now; sending them again later is safe."""


class RecordRejectedError(Exception):
    """The store refused the observations; sending them again would fail the same way."""


class ObservationStore(Protocol):
    """Port: records published observations as versions in the bitemporal core.

    Raises ``StoreUnavailableError`` or ``RecordRejectedError`` when a write fails.
    """

    async def record(
        self, source_id: str, observations: Sequence[PublishedObservation], run_id: str
    ) -> list[RecordedBatch]: ...


@dataclass(frozen=True, slots=True)
class WindowResult:
    window: DateWindow
    delivered_count: int
    """Observations the source delivered for the window."""
    batches: tuple[RecordedBatch, ...]
    last_modified: datetime | None
    """Delivery metadata from the source; not a knowledge time."""

    @property
    def recorded_count(self) -> int:
        return sum(batch.recorded_count for batch in self.batches)

    @property
    def unchanged_count(self) -> int:
        return sum(batch.unchanged_count for batch in self.batches)


@dataclass(frozen=True, slots=True)
class RejectedItem:
    key: str
    reason: str


@dataclass(frozen=True, slots=True)
class DrainResult:
    """What recording the spool's waiting deliveries achieved."""

    recorded: tuple[WindowResult, ...]
    rejected: tuple[RejectedItem, ...]
    """Refused by the store and set aside in the spool."""
    is_blocked: bool
    """The store was unavailable: deliveries are still waiting."""


@dataclass(frozen=True, slots=True)
class LoadResult:
    run_id: str
    windows: tuple[WindowResult, ...]
    """Fetched by this run and recorded."""
    drain: DrainResult
    spooled: tuple[DateWindow, ...]
    """Fetched by this run and spooled, because the store was unavailable."""

    @property
    def is_deferred(self) -> bool:
        """Fetched data waits in the spool instead of being recorded."""
        return bool(self.spooled) or self.drain.is_blocked

    @property
    def delivered_count(self) -> int:
        return sum(window.delivered_count for window in self.windows)

    @property
    def recorded_count(self) -> int:
        return sum(window.recorded_count for window in self.windows)

    @property
    def unchanged_count(self) -> int:
        return sum(window.unchanged_count for window in self.windows)


class LoadPublishedCurve:
    """Record what the spool holds, then fetch each window and record what it delivered.

    Windows run one after another (the source access policy allows no fan-out). A
    window without data is a successful step with zero rows. An invalid delivery or a
    rejected write stops the load; windows recorded before it stay recorded.

    When the store is unavailable, deliveries wait in the spool, oldest first. As long
    as anything waits there, newer deliveries are spooled behind it and never recorded
    directly: an older value recorded after a newer one would become its newer version.
    """

    def __init__(self, source: CurveSource, store: ObservationStore, spool: DeliverySpool) -> None:
        self._source = source
        self._store = store
        self._spool = spool

    async def __call__(self, windows: Sequence[DateWindow], run_id: str) -> LoadResult:
        drain = await self.drain()
        is_blocked = drain.is_blocked
        recorded: list[WindowResult] = []
        spooled: list[DateWindow] = []
        for window in windows:
            delivery = await self._source.fetch(window)
            if not is_blocked or not delivery.observations:
                try:
                    recorded.append(await self._record(delivery, run_id))
                    continue
                except StoreUnavailableError:
                    is_blocked = True
            await self._spool.put(delivery, run_id)
            spooled.append(window)
        return LoadResult(run_id, tuple(recorded), drain, tuple(spooled))

    async def drain(self) -> DrainResult:
        """Record the spool's deliveries in fetch order, until the store is unavailable."""
        recorded: list[WindowResult] = []
        rejected: list[RejectedItem] = []
        for item in await self._spool.pending():
            try:
                recorded.append(await self._record(item.delivery, item.run_id))
            except StoreUnavailableError:
                return DrainResult(tuple(recorded), tuple(rejected), is_blocked=True)
            except RecordRejectedError as error:
                await self._spool.reject(item)
                rejected.append(RejectedItem(item.key, str(error)))
                continue
            await self._spool.remove(item)
        return DrainResult(tuple(recorded), tuple(rejected), is_blocked=False)

    async def _record(self, delivery: Delivery, run_id: str) -> WindowResult:
        batches: list[RecordedBatch] = []
        if delivery.observations:
            batches = await self._store.record(delivery.source_id, delivery.observations, run_id)
        return WindowResult(
            delivery.window, len(delivery.observations), tuple(batches), delivery.last_modified
        )
