"""Client of the persistence service's write interface (anti-corruption layer).

Ingestion never touches the database: it records observations through
``POST /v1/observations/versions`` (``contracts.persistence.v1``). Persistence sets the
knowledge time ``known_from``; nothing the source says about time is sent as one.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from itertools import batched
from types import TracebackType
from typing import Self

import httpx
from contracts.persistence import v1
from pydantic import AwareDatetime, BaseModel, ConfigDict

from ingestion.application.load_published_curve import RecordedBatch
from ingestion.config import PersistenceSettings
from ingestion.domain.observation import PublishedObservation

WRITE_ATTEMPTS = 3
"""Attempts per batch when persistence answers ``409`` (two writers raced to create the
first version of a key; the batch was not stored and is safe to resend)."""
CONFLICT_RETRY_DELAY_SECONDS = 0.5
"""Wait before retry n is ``n`` times this."""


class PersistenceWriteError(Exception):
    """Persistence did not accept a batch. Batches sent before it stay recorded."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"persistence rejected the batch with status {status_code}: {detail}")
        self.status_code = status_code


class _RecordedVersions(BaseModel):
    """Tolerant reader of ``RecordVersionsResponse``: fields added later are ignored."""

    model_config = ConfigDict(extra="ignore")

    recorded_count: int
    unchanged_count: int = 0
    """Added by versioning (#15); absent before it, when nothing can be unchanged."""
    known_from: AwareDatetime


class PersistenceClient:
    """Records published observations in chunks of at most ``MAX_BATCH_SIZE``."""

    def __init__(
        self,
        settings: PersistenceSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sleep = sleep
        self._http = httpx.AsyncClient(
            base_url=str(settings.url), timeout=settings.timeout_seconds, transport=transport
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def record(
        self,
        source_id: str,
        observations: Sequence[PublishedObservation],
        run_id: str,
        delivery_id: str,
    ) -> list[RecordedBatch]:
        """Send the observations as ``published`` versions; one request per chunk.

        Any ``2xx`` is success. ``recorded_count`` counts new versions only: persistence
        treats an unchanged value as a no-op (``unchanged_count``, versioning #15). A
        ``409`` is retried up to ``WRITE_ATTEMPTS`` times; any other error fails at once.
        Batches never repeat an observation: the source schema rejects duplicates.
        """
        return [
            await self._send(_request(source_id, chunk, run_id, delivery_id))
            for chunk in batched(observations, v1.MAX_BATCH_SIZE, strict=False)
        ]

    async def _send(self, request: v1.RecordVersionsRequest) -> RecordedBatch:
        body = request.model_dump_json()
        for attempt in range(1, WRITE_ATTEMPTS + 1):
            response = await self._http.post(
                v1.RECORD_VERSIONS_PATH,
                content=body,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code != httpx.codes.CONFLICT or attempt == WRITE_ATTEMPTS:
                break
            await self._sleep(CONFLICT_RETRY_DELAY_SECONDS * attempt)
        if not response.is_success:
            raise PersistenceWriteError(response.status_code, response.text)
        recorded = _RecordedVersions.model_validate_json(response.content)
        return RecordedBatch(recorded.recorded_count, recorded.unchanged_count, recorded.known_from)


def _request(
    source_id: str, observations: Sequence[PublishedObservation], run_id: str, delivery_id: str
) -> v1.RecordVersionsRequest:
    return v1.RecordVersionsRequest(
        observations=[
            v1.ObservationVersion(
                curve_id=observation.curve_id,
                maturity=observation.maturity,
                valid_date=observation.valid_date,
                value=observation.value,
                origin=v1.Origin.PUBLISHED,
                source_id=source_id,
                run_id=run_id,
                change_reason=v1.ChangeReason.INITIAL,
                normalization_version=observation.normalization_version,
                delivery_id=delivery_id,
            )
            for observation in observations
        ]
    )
