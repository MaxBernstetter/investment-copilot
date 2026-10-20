from datetime import UTC, date, datetime

import httpx
import pytest

from access.domain.curve import (
    CurveNotFoundError,
    InvalidCurveQueryError,
    ProcessingUnavailableError,
)
from access.domain.quality import QualityStatus, Severity
from access.infrastructure.processing import ProcessingClient

pytestmark = pytest.mark.anyio

BASE_URL = "http://processing:8002"
PATH = "/v1/curves/ecb-aaa-spot/value-quality"
QUALITY_PATH = "/v1/curves/ecb-aaa-spot/quality"
AS_OF = datetime(2026, 3, 13, 8, 0, tzinfo=UTC)


def client_answering(handler: httpx.MockTransport) -> ProcessingClient:
    return ProcessingClient(BASE_URL, 5.0, transport=handler)


VALUE_QUALITY_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "valid_from": "2026-03-12",
        "valid_to": "2026-03-12",
        "values": [
            {
                "version_id": 7,
                "maturity": "10Y",
                "valid_date": "2026-03-12",
                "status": "warn",
                "flags": [
                    {
                        "rule": "range",
                        "severity": "warn",
                        "maturity": "10Y",
                        "version_id": 7,
                        "value": 26.4,
                        "explanation": "Yield is outside the plausible range",
                        "evidence": "26.4 % is above 15 %",
                    }
                ],
            }
        ],
    },
    "meta": {"as_of": "2026-03-13T08:00:00Z"},
}


async def test_value_quality_maps_flags() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=VALUE_QUALITY_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        known = await client.value_quality(
            "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), "10Y", AS_OF
        )

    assert seen[0].url.path == PATH
    assert dict(seen[0].url.params) == {
        "from": "2026-03-12",
        "to": "2026-03-12",
        "maturity": "10Y",
        "as_of": AS_OF.isoformat(),
    }
    assert known is not None
    quality = known[7]
    assert quality.status == QualityStatus.WARN
    assert len(quality.flags) == 1
    assert quality.flags[0].rule == "range"
    assert quality.flags[0].severity == Severity.WARN


async def test_processing_errors_return_none() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        assert (
            await client.value_quality(
                "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), None, AS_OF
            )
            is None
        )

    def server_error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with client_answering(httpx.MockTransport(server_error)) as client:
        assert (
            await client.value_quality(
                "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), None, AS_OF
            )
            is None
        )


QUALITY_DAYS_BODY = {
    "data": {
        "curve_id": "ecb-aaa-spot",
        "valid_from": "2026-03-12",
        "valid_to": "2026-03-12",
        "days": [
            {
                "valid_date": "2026-03-12",
                "status": "warn",
                "run_id": "run-42",
                "checked_as_of": "2026-03-13T08:00:00Z",
                "rules": [{"rule": "range", "outcome": "warn", "finding_count": 1}],
                "findings": [
                    {
                        "rule": "range",
                        "severity": "warn",
                        "maturity": "10Y",
                        "version_id": 7,
                        "value": 26.4,
                        "explanation": "Yield is outside the plausible range",
                        "evidence": "26.4 % is above 15 %",
                    }
                ],
            }
        ],
    },
    "meta": {"as_of": "2026-03-13T08:00:00Z"},
}


async def test_quality_days_maps_days_rules_and_findings() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=QUALITY_DAYS_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        result = await client.quality_days(
            "ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF
        )

    assert seen[0].url.path == QUALITY_PATH
    assert dict(seen[0].url.params) == {
        "from": "2026-03-12",
        "to": "2026-03-12",
        "as_of": AS_OF.isoformat(),
    }
    assert result.curve_id == "ecb-aaa-spot"
    assert result.as_of == AS_OF
    assert len(result.days) == 1
    day = result.days[0]
    assert day.valid_date == date(2026, 3, 12)
    assert day.status == QualityStatus.WARN
    assert day.run_id == "run-42"
    assert day.rules[0].rule == "range"
    assert day.rules[0].outcome == QualityStatus.WARN
    assert day.rules[0].finding_count == 1
    assert day.findings[0].rule == "range"
    assert day.findings[0].severity == Severity.WARN
    assert day.findings[0].maturity == "10Y"
    assert day.findings[0].version_id == 7
    assert day.findings[0].value == 26.4


async def test_quality_days_leaves_out_as_of_when_none() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=QUALITY_DAYS_BODY)

    async with client_answering(httpx.MockTransport(answer)) as client:
        await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), None)

    assert dict(seen[0].url.params) == {"from": "2026-03-12", "to": "2026-03-12"}


async def test_quality_days_404_raises_curve_not_found_with_detail() -> None:
    def unknown(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "no curve named ecb-aaa-spot"})

    async with client_answering(httpx.MockTransport(unknown)) as client:
        with pytest.raises(CurveNotFoundError) as raised:
            await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF)

    assert str(raised.value) == "no curve named ecb-aaa-spot"


async def test_quality_days_422_raises_invalid_query() -> None:
    def rejected(_: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "range too long"})

    async with client_answering(httpx.MockTransport(rejected)) as client:
        with pytest.raises(InvalidCurveQueryError):
            await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF)


async def test_quality_days_500_raises_processing_unavailable() -> None:
    def broken(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with client_answering(httpx.MockTransport(broken)) as client:
        with pytest.raises(ProcessingUnavailableError):
            await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF)


async def test_quality_days_transport_error_raises_processing_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_answering(httpx.MockTransport(refuse)) as client:
        with pytest.raises(ProcessingUnavailableError):
            await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF)


async def test_quality_days_malformed_200_body_raises_processing_unavailable() -> None:
    def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with client_answering(httpx.MockTransport(malformed)) as client:
        with pytest.raises(ProcessingUnavailableError):
            await client.quality_days("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), AS_OF)
