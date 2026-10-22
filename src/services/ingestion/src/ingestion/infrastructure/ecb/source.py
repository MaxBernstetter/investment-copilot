"""ECB Data Portal adapter for the euro area spot curves, AAA and all issuers.

See ``docs/project/00-data-ingestion``. Both curves on the whole grid cost one request
per window: instruments and series are joined with ``+``.
"""

from email.utils import parsedate_to_datetime

import httpx

from ingestion.domain.delivery import RawDelivery
from ingestion.domain.observation import PublishedObservation
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.ecb.payload import DATA_TYPES, INSTRUMENTS, parse_payload, series_key
from ingestion.infrastructure.http import Outcome, SourceClient

SOURCE_ID = "ecb"
DATA_URL = "https://data-api.ecb.europa.eu/service/data/YC/" + series_key(
    "+".join(INSTRUMENTS), "+".join(DATA_TYPES)
)

NO_DATA_MESSAGES = ("No results found", "No Series was returned")
"""How the API words its ``404`` for a query without data (the second is what it sends
for an ``updatedAfter`` without changes, as recorded on 2026-10-18)."""


def is_no_data(response: httpx.Response) -> bool:
    """The ECB's ``404`` "no data" answer: an empty delivery, never retried."""
    return response.status_code == httpx.codes.NOT_FOUND and any(
        message in response.text for message in NO_DATA_MESSAGES
    )


class EcbSpotCurveSource:
    """Fetches one window of the grid through the polite source client, and parses it."""

    def __init__(self, client: SourceClient) -> None:
        self._client = client

    async def fetch(self, window: DateWindow) -> RawDelivery:
        """The answer as received. Only a delivered, non-empty body is a payload."""
        response = await self._client.get(
            DATA_URL,
            params={
                "startPeriod": window.start.isoformat(),
                "endPeriod": window.end.isoformat(),
                "format": "csvdata",
                "detail": "dataonly",
            },
        )
        has_payload = response.outcome is Outcome.DELIVERED and bool(response.content)
        last_modified = response.headers.get("Last-Modified")
        return RawDelivery(
            source_id=SOURCE_ID,
            request_url=response.url,
            response_status=response.status_code,
            fetched_at=response.fetched_at,
            last_modified=parsedate_to_datetime(last_modified) if last_modified else None,
            etag=response.headers.get("ETag"),
            payload=response.content if has_payload else None,
        )

    def parse(self, delivery: RawDelivery) -> list[PublishedObservation]:
        return parse_delivery(delivery)


def parse_delivery(delivery: RawDelivery) -> list[PublishedObservation]:
    """Validate and map the payload; raises ``InvalidPayloadError`` if it breaks the schema.

    Needs no client: replay parses stored deliveries with it.
    """
    return parse_payload(delivery.payload) if delivery.payload is not None else []
