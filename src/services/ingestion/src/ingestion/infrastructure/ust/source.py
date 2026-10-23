"""US Treasury Daily Treasury Par Yield Curve Rates: the adapter (#266).

One request per calendar year. The Treasury answers a year without data with HTTP 200 and an
empty body, which is an empty delivery and not an error.
"""

import logging

import httpx
from opentelemetry.metrics import Meter, NoOpMeter

from ingestion.domain.delivery import RawDelivery
from ingestion.domain.observation import PublishedObservation
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.http import Outcome, SourceClient
from ingestion.infrastructure.ust.payload import parse_payload

logger = logging.getLogger(__name__)

SOURCE_ID = "ust"
UST_DATA_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)
"""The yearly CSV of the daily par yield curve. A constant, not a setting (as the ECB URL)."""
SCHEMA_CHANGES_METRIC = "ingestion_compatible_schema_changes_total"
"""Counter of compatible schema changes (unknown columns), by ``source_id``."""


def is_no_data(response: httpx.Response) -> bool:
    """Never: the Treasury's answer for a year without data is HTTP 200 with an empty body.

    That is recorded as an empty delivery by ``UstParCurveSource.fetch`` (no payload), so no
    status code needs to be read as "no data". Nothing is retried on a 200.
    """
    return False


class UstParCurveSource:
    """Fetches the year of a window through the polite source client, and parses it."""

    def __init__(self, client: SourceClient, meter: Meter | None = None) -> None:
        self._client = client
        self._meter = meter or NoOpMeter(SOURCE_ID)

    async def fetch(self, window: DateWindow) -> RawDelivery:
        """The year of ``window.end``, as received. Only a delivered, non-empty body is a payload.

        A window that spans New Year fetches only the year of its end: the days of the earlier
        year are covered by their own daily runs and by the backfill.
        """
        response = await self._client.get(UST_DATA_URL.format(year=window.end.year))
        has_payload = response.outcome is Outcome.DELIVERED and bool(response.content)
        return RawDelivery(
            source_id=SOURCE_ID,
            request_url=response.url,
            response_status=response.status_code,
            fetched_at=response.fetched_at,
            last_modified=None,
            etag=None,
            payload=response.content if has_payload else None,
        )

    def parse(self, delivery: RawDelivery) -> list[PublishedObservation]:
        return parse_delivery(delivery, self._meter)


def parse_delivery(delivery: RawDelivery, meter: Meter | None = None) -> list[PublishedObservation]:
    """All rows of the yearly file (no window clipping: unchanged values are no-ops downstream).

    Unknown columns are accepted and reported once per delivery: logged and counted in
    ``SCHEMA_CHANGES_METRIC``. Raises ``InvalidPayloadError`` if the payload breaks the declared
    schema. Needs no client: replay parses stored deliveries with it (no meter: nothing counted).
    """
    if delivery.payload is None:
        return []
    observations, unknown_columns = parse_payload(delivery.payload)
    if unknown_columns:
        logger.warning(
            "ust_unknown_columns",
            extra={"source": SOURCE_ID, "unknown_columns": list(unknown_columns)},
        )
        (meter or NoOpMeter(SOURCE_ID)).create_counter(
            SCHEMA_CHANGES_METRIC,
            unit="1",
            description="Compatible schema changes (unknown columns) seen in a delivery",
        ).add(1, {"source_id": SOURCE_ID})
    return observations
