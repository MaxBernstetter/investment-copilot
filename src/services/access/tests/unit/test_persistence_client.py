from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from access.domain.changes import CurveChanges, ValueChange
from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.domain.series import Series, SeriesPoint
from access.domain.versions import ChangeReason, ValueVersion, ValueVersions
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


SERIES_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations"
SERIES_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "maturity": "10Y",
        "points": [
            {"valid_date": "2026-03-12", "value": 2.61},
            {"valid_date": "2026-03-14", "value": 2.7},
        ],
    },
    "meta": {"as_of": "2026-03-13T08:00:00Z"},
}


async def test_reads_a_series_from_persistence() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SERIES_BODY)

    as_of = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    async with client_answering(httpx.MockTransport(answer)) as client:
        series = await client.series_as_of(
            "ecb-aaa-spot", "10Y", date(2026, 3, 1), date(2026, 3, 14), as_of
        )

    assert seen[0].url.path == SERIES_PATH
    assert dict(seen[0].url.params) == {
        "from": "2026-03-01",
        "to": "2026-03-14",
        "as_of": "2026-03-13T09:00:00+01:00",
    }
    assert series == Series(
        curve_id="ecb-aaa-spot",
        maturity="10Y",
        as_of=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
        points=(
            SeriesPoint(valid_date=date(2026, 3, 12), value=2.61),
            SeriesPoint(valid_date=date(2026, 3, 14), value=2.7),
        ),
    )


async def test_omits_absent_series_parameters() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SERIES_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        await client.series_as_of("ecb-aaa-spot", "10Y", None, None, None)

    assert seen[0].url.query == b""


async def test_series_not_found_problem_becomes_curve_not_found() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"type": "about:blank", "title": "Not found", "status": 404, "detail": "no 4Y"},
            headers={"content-type": "application/problem+json"},
        )

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(CurveNotFoundError) as raised:
            await client.series_as_of("ecb-aaa-spot", "4Y", None, None, None)

    assert raised.value.detail == "no 4Y"


async def test_series_invalid_range_problem_becomes_invalid_query() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"type": "about:blank", "title": "Invalid range", "status": 422, "detail": "bad"},
        )

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(InvalidCurveQueryError) as raised:
            await client.series_as_of("ecb-aaa-spot", "10Y", None, None, None)

    assert raised.value.detail == "bad"


async def test_series_server_error_is_unavailable() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.series_as_of("ecb-aaa-spot", "10Y", None, None, None)


async def test_series_connection_error_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.series_as_of("ecb-aaa-spot", "10Y", None, None, None)


VERSIONS_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations/2026-03-12/versions"
VERSIONS_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "maturity": "10Y",
        "valid_date": "2026-03-12",
        "versions": [
            {
                "version_id": 4711,
                "value": 2.61,
                "known_from": "2026-03-13T08:00:00Z",
                "known_to": "2026-03-14T08:00:00Z",
                "source_id": "ecb",
                "run_id": "run-1",
                "change_reason": "initial",
                "normalization_version": "1",
                "delivery_id": "4711",
            },
            {
                "version_id": 4712,
                "value": 2.7,
                "known_from": "2026-03-14T08:00:00Z",
                "known_to": None,
                "source_id": "ecb",
                "run_id": "run-2",
                "change_reason": "correction",
                "normalization_version": "1",
                "delivery_id": None,
            },
        ],
    },
    "meta": {"as_of": "2026-03-15T08:00:00Z"},
}


async def test_reads_value_versions() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=VERSIONS_BODY)

    as_of = datetime(2026, 3, 15, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    async with client_answering(httpx.MockTransport(answer)) as client:
        versions = await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), as_of)

    assert seen[0].url.path == VERSIONS_PATH
    assert dict(seen[0].url.params) == {"as_of": "2026-03-15T09:00:00+01:00"}
    assert versions == ValueVersions(
        curve_id="ecb-aaa-spot",
        maturity="10Y",
        valid_date=date(2026, 3, 12),
        as_of=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
        versions=(
            ValueVersion(
                version_id=4711,
                value=2.61,
                known_from=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
                known_to=datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
                source_id="ecb",
                run_id="run-1",
                change_reason=ChangeReason.INITIAL,
                normalization_version="1",
                delivery_id="4711",
            ),
            ValueVersion(
                version_id=4712,
                value=2.7,
                known_from=datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
                known_to=None,
                source_id="ecb",
                run_id="run-2",
                change_reason=ChangeReason.CORRECTION,
                normalization_version="1",
                delivery_id=None,
            ),
        ),
    )


async def test_value_versions_not_found() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"type": "about:blank", "title": "Not found", "status": 404, "detail": "no 4Y"},
            headers={"content-type": "application/problem+json"},
        )

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(CurveNotFoundError) as raised:
            await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), None)

    assert raised.value.detail == "no 4Y"


async def test_value_versions_invalid_query_is_invalid_query() -> None:
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
        with pytest.raises(InvalidCurveQueryError):
            await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), None)


async def test_value_versions_unavailable() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), None)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), None)

    def garbage(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    async with client_answering(httpx.MockTransport(garbage)) as client:
        with pytest.raises(PersistenceUnavailableError):
            await client.value_versions("ecb-aaa-spot", "10Y", date(2026, 3, 12), None)


CHANGES_PATH = "/v1/curves/ecb-aaa-spot/changes"
CHANGES_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "valid_from": "2026-03-12",
        "valid_to": "2026-03-14",
        "changes": [
            {
                "valid_date": "2026-03-12",
                "maturity": "10Y",
                "old_value": 2.61,
                "new_value": 2.7,
                "change_reason": "correction",
                "source_id": "ecb",
                "known_from": "2026-03-14T08:00:00Z",
            },
        ],
    },
    "meta": {"since": "2026-03-13T08:00:00Z", "as_of": "2026-03-15T08:00:00Z"},
}


async def test_reads_changes() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CHANGES_BODY)

    since = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    as_of = datetime(2026, 3, 15, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    async with client_answering(httpx.MockTransport(answer)) as client:
        changes = await client.changes(
            "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), since, as_of
        )

    assert seen[0].url.path == CHANGES_PATH
    assert dict(seen[0].url.params) == {
        "from": "2026-03-12",
        "to": "2026-03-14",
        "since": "2026-03-13T09:00:00+01:00",
        "as_of": "2026-03-15T09:00:00+01:00",
    }
    assert changes == CurveChanges(
        curve_id="ecb-aaa-spot",
        valid_from=date(2026, 3, 12),
        valid_to=date(2026, 3, 14),
        since=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
        as_of=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
        changes=(
            ValueChange(
                valid_date=date(2026, 3, 12),
                maturity="10Y",
                old_value=2.61,
                new_value=2.7,
                change_reason=ChangeReason.CORRECTION,
                source_id="ecb",
                known_from=datetime(2026, 3, 14, 8, 0, tzinfo=UTC),
            ),
        ),
    )


async def test_changes_omit_as_of_when_absent() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CHANGES_BODY)

    since = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)
    async with client_answering(httpx.MockTransport(answer)) as client:
        await client.changes("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), since, None)

    assert "as_of" not in seen[0].url.params


async def test_changes_not_found() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"type": "about:blank", "title": "Not found", "status": 404, "detail": "no curve"},
            headers={"content-type": "application/problem+json"},
        )

    since = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)
    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(CurveNotFoundError) as raised:
            await client.changes("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), since, None)

    assert raised.value.detail == "no curve"


async def test_changes_invalid_query_is_invalid_query() -> None:
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

    since = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)
    async with client_answering(httpx.MockTransport(answer)) as client:
        with pytest.raises(InvalidCurveQueryError):
            await client.changes("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), since, None)


async def test_changes_unavailable() -> None:
    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    def garbage(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    since = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)
    for handler in (answer, refuse, garbage):
        async with client_answering(httpx.MockTransport(handler)) as client:
            with pytest.raises(PersistenceUnavailableError):
                await client.changes(
                    "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), since, None
                )
