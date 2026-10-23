"""The US Treasury adapter: one request per year, the empty answer and the parse hand-over."""

import logging
from datetime import UTC, date, datetime

import httpx
import pytest
from opentelemetry.metrics import NoOpMeter

from ingestion.config import SourceSettings
from ingestion.domain.delivery import RawDelivery
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.http import SourceClient
from ingestion.infrastructure.ust import UstParCurveSource, is_no_data, parse_delivery
from tests.recorded import (
    UST_EMPTY_2027,
    UST_NEW_COLUMN_2025,
    UST_YEAR_1990,
    UST_YEAR_2025,
    ust_payload,
    ust_response,
)

WINDOW_2025 = DateWindow(date(2025, 12, 22), date(2025, 12, 31))
URL_2025 = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/2025/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value=2025&page&_format=csv"
)


async def fetch(window: DateWindow, answer: httpx.Response) -> RawDelivery:
    async with SourceClient(
        "ust",
        SourceSettings(min_interval_seconds=0),
        is_no_data=is_no_data,
        transport=httpx.MockTransport(lambda _request: answer),
        meter=NoOpMeter("test"),
    ) as client:
        return await UstParCurveSource(client).fetch(window)


@pytest.mark.anyio
async def test_a_year_is_fetched_with_one_request_and_keeps_its_body() -> None:
    delivery = await fetch(WINDOW_2025, ust_response(UST_YEAR_2025))

    assert delivery.request_url == URL_2025
    assert delivery.payload == ust_payload(UST_YEAR_2025)
    assert (delivery.response_status, delivery.etag, delivery.last_modified) == (200, None, None)


@pytest.mark.anyio
async def test_a_window_across_new_year_fetches_the_year_of_its_end() -> None:
    delivery = await fetch(
        DateWindow(date(2025, 12, 29), date(2026, 1, 2)), ust_response(UST_YEAR_2025)
    )

    assert delivery.request_url.endswith(
        "/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv"
    )


@pytest.mark.anyio
async def test_a_year_without_data_is_a_delivery_without_payload() -> None:
    answer = ust_response(UST_EMPTY_2027)

    delivery = await fetch(DateWindow(date(2027, 1, 1), date(2027, 1, 8)), answer)

    assert (delivery.response_status, delivery.payload) == (200, None)
    assert parse_delivery(delivery) == []


@pytest.mark.anyio
async def test_the_first_year_of_the_history_parses_its_own_header() -> None:
    delivery = await fetch(
        DateWindow(date(1990, 12, 24), date(1990, 12, 31)), ust_response(UST_YEAR_1990)
    )

    assert len(parse_delivery(delivery)) == 5 * 9


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(ust_response(UST_YEAR_2025), id="delivery"),
        pytest.param(httpx.Response(404, text="<html>Not Found</html>"), id="other 404"),
        pytest.param(httpx.Response(200, content=b""), id="empty 200"),
    ],
)
def test_no_answer_is_read_as_no_data(answer: httpx.Response) -> None:
    assert not is_no_data(answer)


def test_unknown_columns_are_logged_once_per_delivery(caplog: pytest.LogCaptureFixture) -> None:
    delivery = RawDelivery(
        source_id="ust",
        request_url=URL_2025,
        response_status=200,
        fetched_at=datetime(2026, 10, 23, tzinfo=UTC),
        last_modified=None,
        etag=None,
        payload=ust_payload(UST_NEW_COLUMN_2025),
    )

    with caplog.at_level(logging.WARNING, logger="ingestion.infrastructure.ust.source"):
        observations = parse_delivery(delivery)

    records = [r for r in caplog.records if r.getMessage() == "ust_unknown_columns"]
    assert len(records) == 1
    assert records[0].unknown_columns == ["9 Mo"]  # type: ignore[attr-defined]
    assert observations


@pytest.mark.anyio
async def test_the_source_parses_its_own_delivery() -> None:
    async with SourceClient(
        "ust",
        SourceSettings(min_interval_seconds=0),
        is_no_data=is_no_data,
        transport=httpx.MockTransport(lambda _request: ust_response(UST_YEAR_2025)),
        meter=NoOpMeter("test"),
    ) as client:
        source = UstParCurveSource(client)
        delivery = await source.fetch(WINDOW_2025)

        assert len(source.parse(delivery)) == 4 * 14 - 2
