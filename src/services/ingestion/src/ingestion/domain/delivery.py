"""A source's answer to one request, kept byte for byte: the raw stage (``ING``)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawDelivery:
    """What a source answered to one request, exactly as received.

    It is stored before it is parsed, so every stored value can be traced back to it and
    replay parses it again instead of calling the source.
    """

    source_id: str
    request_url: str
    """The full request URL, query string included."""
    response_status: int
    fetched_at: datetime
    """When the answer arrived (UTC)."""
    last_modified: datetime | None
    """The source's publication time of its latest change: delivery metadata only,
    never the knowledge time (that is when YieldLens stores a value)."""
    etag: str | None
    payload: bytes | None
    """The response body byte for byte; ``None`` for an empty delivery (the source's
    "no data" answer, ``304``, or an empty body)."""
