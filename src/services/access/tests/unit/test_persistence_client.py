from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.infrastructure.persistence import PersistenceClient

pytestmark = pytest.mark.anyio

BASE_URL = "http://persistence:8001"


def client_answering(handler: httpx.MockTransport) -> PersistenceClient:
    return PersistenceClient(BASE_URL, 5.0, transport=handler)


async def test_is_ready_when_persistence_answers_200() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ready"
        return httpx.Response(200, json={"status": "ready"})

    async with client_answering(httpx.MockTransport(answer)) as client:
        assert await client.is_ready() is True


async def test_is_not_ready_when_persistence_answers_503() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "unavailable"})

    async with client_answering(httpx.MockTransport(answer)) as client:
        assert await client.is_ready() is False


async def test_is_not_ready_when_persistence_is_unreachable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        assert await client.is_ready() is False


CURVE_PATH = "/v1/curves/ecb-aaa-spot/observations"
CURVE_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "valid_date": "2026-03-12",
        "points": [
            {"maturity": "3M", "months": 3, "value": None},
            {"maturity": "10Y", "months": 120, "value": 2.61},
        ],
    },
    "meta": {"as_of": "2026-03-13T08:00:00Z"},
}


async def test_reads_a_curve_from_persistence() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CURVE_BODY)

    as_of = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    async with client_answering(httpx.MockTransport(answer)) as client:
        curve = await client.curve_as_of("ecb-aaa-spot", date(2026, 3, 12), as_of)

    assert seen[0].url.path == CURVE_PATH
    assert dict(seen[0].url.params) == {
        "valid_date": "2026-03-12",
        "as_of": "2026-03-13T09:00:00+01:00",
    }
    assert curve == CurveAsOf(
        curve_id="ecb-aaa-spot",
        valid_date=date(2026, 3, 12),
        as_of=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
        points=(
            CurvePoint(maturity="3M", months=3, value=None),
            CurvePoint(maturity="10Y", months=120, value=2.61),
        ),
    )


async def test_omits_absent_parameters() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CURVE_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        await client.curve_as_of("ecb-aaa-spot", None, None)

    assert seen[0].url.query == b""


async def test_not_found_problem_becomes_curve_not_found() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"type": "about:blank", "title": "Not found", "status": 404, "detail": "no curve"},
            headers={"content-type": "application/problem+json"},
        )

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(CurveNotFoundError) as raised:
            await client.curve_as_of("ecb-aaa-spot", None, None)

    assert raised.value.detail == "no curve"


async def test_invalid_request_problem_becomes_invalid_query() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "type": "about:blank",
                "title": "Invalid request",
                "status": 422,
                "detail": "bad",
            },
        )

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(InvalidCurveQueryError) as raised:
            await client.curve_as_of("ecb-aaa-spot", None, None)

    assert raised.value.detail == "bad"


async def test_server_error_is_unavailable() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.curve_as_of("ecb-aaa-spot", None, None)


async def test_connection_error_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.curve_as_of("ecb-aaa-spot", None, None)
