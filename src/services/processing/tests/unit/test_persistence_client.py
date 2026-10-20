from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from processing.infrastructure.persistence import PersistenceClient, PersistenceReadError

pytestmark = pytest.mark.anyio

BASE_URL = "http://persistence:8001"
CURVE_PATH = "/v1/curves/ecb-aaa-spot/observations"
SERIES_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations"
CHECKED_AS_OF = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)

CURVE_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "valid_date": "2026-03-12",
        "points": [
            {"maturity": "3M", "months": 3, "value": None, "version_id": None},
            {"maturity": "10Y", "months": 120, "value": 2.61, "version_id": 7},
        ],
    },
    "meta": {"as_of": "2026-03-13T08:00:00Z"},
}


def client_answering(handler: httpx.MockTransport) -> PersistenceClient:
    return PersistenceClient(BASE_URL, 5.0, transport=handler)


async def test_grid_reads_the_latest_curve_and_its_knowledge_time() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CURVE_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        grid = await client.grid("ecb-aaa-spot")

    assert seen[0].url.path == CURVE_PATH
    assert seen[0].url.query == b""
    assert grid is not None
    assert grid.maturities == ("3M", "10Y")
    assert grid.as_of == CHECKED_AS_OF


async def test_series_404_is_empty() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == SERIES_PATH
        return httpx.Response(404, json={"detail": "no series"})

    async with client_answering(httpx.MockTransport(answer)) as client:
        points = await client.series(
            "ecb-aaa-spot",
            "10Y",
            date(2026, 10, 1),
            date(2026, 10, 8),
            CHECKED_AS_OF,
        )

    assert points == []


async def test_values_are_decimals_from_their_text() -> None:
    body = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "points": [{"valid_date": "2026-10-06", "value": 2.87, "version_id": 3}],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z"},
    }
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    async with client_answering(httpx.MockTransport(answer)) as client:
        points = await client.series(
            "ecb-aaa-spot",
            "10Y",
            date(2026, 10, 6),
            date(2026, 10, 6),
            CHECKED_AS_OF,
        )

    assert points[0].value == Decimal("2.87")
    assert seen[0].url.params["from"] == "2026-10-06"
    assert seen[0].url.params["to"] == "2026-10-06"
    assert seen[0].url.params["as_of"] == CHECKED_AS_OF.isoformat()


def _raise_connect_error(_: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection failed")


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(
            lambda _: httpx.Response(503, json={"detail": "unavailable"}),
            id="503",
        ),
        pytest.param(_raise_connect_error, id="connect_error"),
        pytest.param(
            lambda _: httpx.Response(200, json={"unexpected": "shape"}),
            id="malformed_body",
        ),
    ],
)
async def test_other_statuses_raise_persistence_read_error(
    answer: Callable[[httpx.Request], httpx.Response],
) -> None:
    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(PersistenceReadError):
            await client.grid("ecb-aaa-spot")
