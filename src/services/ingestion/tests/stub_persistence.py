"""A stand-in for the persistence write interface, checked against its contract.

It answers like persistence with versioning (#15): ``recorded_count`` new versions plus
``unchanged_count`` no-ops add up to the batch size.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import chain, repeat

import httpx
from contracts.persistence import v1

KNOWN_FROM = datetime(2026, 10, 18, 9, 30, 0, 123456, tzinfo=UTC)
"""The knowledge time the stub's database clock sets."""

URL = "http://persistence.test:8001"


@dataclass
class StubPersistence:
    """Records each accepted batch; answers like persistence does for an empty store."""

    statuses: list[int] = field(default_factory=list)
    """Status of the first requests in order; ``200`` after them."""
    unchanged_count: int = 0
    """Observations of each batch reported as unchanged (already stored)."""
    include_unchanged_count: bool = True
    """``False`` answers like persistence before versioning (no ``unchanged_count``)."""
    is_reachable: bool = True
    """``False`` refuses every connection, like a persistence api that is down."""
    batches: list[v1.RecordVersionsRequest] = field(default_factory=list)
    attempts: int = 0
    _next_status: Iterator[int] = field(init=False)

    def __post_init__(self) -> None:
        self._next_status = chain(self.statuses, repeat(200))

    def handle(self, request: httpx.Request) -> httpx.Response:
        if not self.is_reachable:
            raise httpx.ConnectError("connection refused", request=request)
        assert request.method == "POST"
        assert request.url.path == v1.RECORD_VERSIONS_PATH
        batch = v1.RecordVersionsRequest.model_validate_json(request.content)
        self.attempts += 1
        status_code = next(self._next_status)
        if status_code != 200:
            return httpx.Response(
                status_code,
                json={"title": "Rejected", "status": status_code},
                headers={"Content-Type": "application/problem+json"},
            )
        self.batches.append(batch)
        body: dict[str, object] = v1.RecordVersionsResponse(
            recorded_count=len(batch.observations) - self.unchanged_count,
            known_from=KNOWN_FROM,
        ).model_dump(mode="json")
        if self.include_unchanged_count:
            body["unchanged_count"] = self.unchanged_count
        return httpx.Response(200, json=body)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @property
    def observations(self) -> list[v1.ObservationVersion]:
        return [observation for batch in self.batches for observation in batch.observations]
