"""ECB Data Portal adapter for the euro area AAA spot curve (``docs/project/00-data-ingestion``).

The whole grid costs one request per window: the 11 series are joined with ``+``.
"""

from email.utils import parsedate_to_datetime

import httpx

from ingestion.domain.observation import Delivery
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.ecb.payload import DATA_TYPES, SERIES_PREFIX, parse_payload
from ingestion.infrastructure.http import Outcome, SourceClient

SOURCE_ID = "ecb"
DATA_URL = "https://data-api.ecb.europa.eu/service/data/YC/" + SERIES_PREFIX + "+".join(DATA_TYPES)

NO_DATA_MESSAGES = ("No results found", "No Series was returned")
"""How the API words its ``404`` for a query without data (the second is what it sends
for an ``updatedAfter`` without changes, as recorded on 2026-10-18)."""


def is_no_data(response: httpx.Response) -> bool:
    """The ECB's ``404`` "no data" answer: an empty delivery, never retried."""
    return response.status_code == httpx.codes.NOT_FOUND and any(
        message in response.text for message in NO_DATA_MESSAGES
    )


class EcbSpotCurveSource:
    """Fetches one window of the grid through the polite source client and validates it."""

    def __init__(self, client: SourceClient) -> None:
        self._client = client

    async def fetch(self, window: DateWindow) -> Delivery:
        response = await self._client.get(
            DATA_URL,
            params={
                "startPeriod": window.start.isoformat(),
                "endPeriod": window.end.isoformat(),
                "format": "csvdata",
                "detail": "dataonly",
            },
        )
        observations = (
            parse_payload(response.content) if response.outcome is Outcome.DELIVERED else []
        )
        last_modified = response.headers.get("Last-Modified")
        return Delivery(
            source_id=SOURCE_ID,
            window=window,
            observations=tuple(observations),
            last_modified=parsedate_to_datetime(last_modified) if last_modified else None,
        )
