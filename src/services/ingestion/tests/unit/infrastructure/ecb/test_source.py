from datetime import date

import httpx
import pytest
from opentelemetry.metrics import NoOpMeter

from ingestion.config import SourceSettings
from ingestion.domain.delivery import RawDelivery
from ingestion.domain.windows import DateWindow
from ingestion.infrastructure.ecb import EcbSpotCurveSource, is_no_data
from ingestion.infrastructure.http import SourceClient
from tests.recorded import DAILY, NO_SERIES_404, payload, recorded_response

WINDOW = DateWindow(date(2026, 10, 1), date(2026, 10, 15))


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(recorded_response(NO_SERIES_404), id="recorded 404 for updatedAfter"),
        pytest.param(httpx.Response(404, text="No results found."), id="documented wording"),
    ],
)
def test_the_ecb_no_data_answer_is_recognised(response: httpx.Response) -> None:
    assert is_no_data(response)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(recorded_response(DAILY), id="delivery"),
        pytest.param(httpx.Response(404, text="<html>Not Found</html>"), id="other 404"),
        pytest.param(httpx.Response(400, text="No results found"), id="other status"),
    ],
)
def test_other_answers_are_not_no_data(response: httpx.Response) -> None:
    assert not is_no_data(response)


async def fetch_and_parse(answer: httpx.Response) -> tuple[RawDelivery, int]:
    """Fetch WINDOW answered by ``answer``; returns the delivery and its observation count."""
    async with SourceClient(
        "ecb",
        SourceSettings(min_interval_seconds=0),
        is_no_data=is_no_data,
        transport=httpx.MockTransport(lambda _request: answer),
        meter=NoOpMeter("test"),
    ) as client:
        source = EcbSpotCurveSource(client)
        delivery = await source.fetch(WINDOW)
        return delivery, len(source.parse(delivery))


@pytest.mark.anyio
async def test_a_delivered_answer_keeps_its_body_and_validators() -> None:
    answer = recorded_response(DAILY)
    answer.headers["ETag"] = '"v7"'

    delivery, parsed = await fetch_and_parse(answer)

    assert delivery.payload == payload(DAILY)
    assert (delivery.response_status, delivery.etag) == (200, '"v7"')
    assert "startPeriod=2026-10-01&endPeriod=2026-10-15" in delivery.request_url
    assert parsed == 121


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(recorded_response(NO_SERIES_404), id="ECB 404 no data"),
        pytest.param(httpx.Response(304, headers={"ETag": '"v7"'}), id="304 not modified"),
        pytest.param(httpx.Response(200, content=b""), id="200 with empty body"),
    ],
)
async def test_an_empty_answer_is_a_delivery_without_payload(answer: httpx.Response) -> None:
    delivery, parsed = await fetch_and_parse(answer)

    assert (delivery.response_status, delivery.payload, parsed) == (answer.status_code, None, 0)
