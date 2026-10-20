from datetime import UTC, date, datetime

import httpx
import pytest

from access.domain.quality import QualityStatus, Severity
from access.infrastructure.processing import ProcessingClient

pytestmark = pytest.mark.anyio

BASE_URL = "http://processing:8002"
PATH = "/v1/curves/ecb-aaa-spot/value-quality"
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
