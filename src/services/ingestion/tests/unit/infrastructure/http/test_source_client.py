"""SourceClient against a local stub transport and a fake clock. No live source is called."""

import asyncio
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from opentelemetry.metrics import NoOpMeter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from ingestion.config import SourceSettings
from ingestion.infrastructure.http import (
    Outcome,
    SourceClient,
    SourceDisabledError,
    SourceRequestError,
)

pytestmark = pytest.mark.anyio

URL = "https://source.example/data"
START = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

Answer = httpx.Response | Exception


@dataclass
class FakeClock:
    """Time only moves when the client sleeps."""

    elapsed: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.elapsed

    def now(self) -> datetime:
        return START + timedelta(seconds=self.elapsed)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.elapsed += seconds
        await asyncio.sleep(0)


@dataclass
class StubSource:
    """Answers requests from a script and records what it received, and when."""

    clock: FakeClock
    answers: Iterator[Answer]
    requests: list[httpx.Request] = field(default_factory=list)
    request_times: list[float] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.request_times.append(self.clock.monotonic())
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return answer


def settings(**overrides: object) -> SourceSettings:
    values: dict[str, object] = {"min_interval_seconds": 0.0, "backoff_base_seconds": 1.0}
    values.update(overrides)
    return SourceSettings.model_validate(values)


@dataclass
class Harness:
    clock: FakeClock = field(default_factory=FakeClock)
    reader: InMemoryMetricReader = field(default_factory=InMemoryMetricReader)

    def __post_init__(self) -> None:
        self.meter = MeterProvider(metric_readers=[self.reader]).get_meter("test")

    def make(
        self,
        *answers: Answer,
        source_settings: SourceSettings | None = None,
        is_no_data: Callable[[httpx.Response], bool] | None = None,
        jitter: float = 1.0,
    ) -> tuple[SourceClient, StubSource]:
        stub = StubSource(self.clock, iter(answers))
        extra = {"is_no_data": is_no_data} if is_no_data else {}
        client = SourceClient(
            "ecb",
            source_settings or settings(),
            transport=httpx.MockTransport(stub.handle),
            clock=self.clock,
            jitter=lambda: jitter,
            meter=self.meter,
            **extra,
        )
        return client, stub

    def request_counts(self) -> dict[tuple[str, str], int]:
        data = self.reader.get_metrics_data()
        counts: dict[tuple[str, str], int] = {}
        if data is None:
            return counts
        for resource_metrics in data.resource_metrics:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name != "yl_ingestion_source_requests_total":
                        continue
                    for point in metric.data.data_points:
                        attributes = point.attributes or {}
                        key = (str(attributes["source"]), str(attributes["status"]))
                        counts[key] = int(point.value)  # type: ignore[union-attr]
        return counts


@pytest.fixture
def harness() -> Harness:
    return Harness()


def ok(content: bytes = b"KEY,TIME_PERIOD,OBS_VALUE\n") -> httpx.Response:
    return httpx.Response(
        200, content=content, headers={"Last-Modified": "Thu, 15 Oct 2026 10:00:00 GMT"}
    )


# --- delivery and identification ---------------------------------------------------------


async def test_delivers_the_payload_with_its_headers(harness: Harness) -> None:
    client, _ = harness.make(ok(b"payload"))

    async with client:
        response = await client.get(URL, params={"format": "csvdata"})

    assert response.outcome is Outcome.DELIVERED
    assert response.content == b"payload"
    assert response.headers["Last-Modified"] == "Thu, 15 Oct 2026 10:00:00 GMT"
    assert response.url == URL + "?format=csvdata"
    assert response.fetched_at == START


async def test_identifies_as_yieldlens_without_personal_contact_data(harness: Harness) -> None:
    client, stub = harness.make(ok())

    async with client:
        await client.get(URL)

    user_agent = stub.requests[0].headers["User-Agent"]
    assert re.fullmatch(
        r"YieldLens/\d+\.\d+\.\d+ \(\+https://github\.com/MaxBernstetter/yield-lens\)",
        user_agent,
    )
    assert "@" not in user_agent


# --- pacing and concurrency ----------------------------------------------------------------


async def test_keeps_the_minimum_interval_between_requests(harness: Harness) -> None:
    client, stub = harness.make(ok(), ok(), ok(), source_settings=settings(min_interval_seconds=2))

    async with client:
        for _ in range(3):
            await client.get(URL)

    assert stub.request_times == [0.0, 2.0, 4.0]


async def test_does_not_wait_when_the_interval_has_already_passed(harness: Harness) -> None:
    client, stub = harness.make(ok(), ok(), source_settings=settings(min_interval_seconds=2))

    async with client:
        await client.get(URL)
        harness.clock.elapsed += 10
        await client.get(URL)

    assert stub.request_times == [0.0, 10.0]
    assert harness.clock.sleeps == []


@pytest.mark.parametrize("limit", [1, 2])
async def test_limits_concurrent_requests(harness: Harness, limit: int) -> None:
    in_flight = 0
    peak = 0

    async def slow_source(_request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        for _ in range(5):
            await asyncio.sleep(0)
        in_flight -= 1
        return ok()

    client = SourceClient(
        "ecb",
        settings(max_concurrent_requests=limit),
        transport=httpx.MockTransport(slow_source),
        clock=harness.clock,
        meter=NoOpMeter("test"),
    )
    async with client:
        await asyncio.gather(*(client.get(URL) for _ in range(4)))

    assert peak == limit


# --- retries ---------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_retries_throttling_and_unavailability(harness: Harness, status: int) -> None:
    client, stub = harness.make(httpx.Response(status), ok())

    async with client:
        response = await client.get(URL)

    assert response.outcome is Outcome.DELIVERED
    assert len(stub.requests) == 2


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("refused"),
    ],
)
async def test_retries_timeouts_and_network_errors(harness: Harness, error: Exception) -> None:
    client, stub = harness.make(error, ok())

    async with client:
        response = await client.get(URL)

    assert response.outcome is Outcome.DELIVERED
    assert len(stub.requests) == 2


async def test_gives_up_after_three_attempts(harness: Harness) -> None:
    client, stub = harness.make(*(httpx.Response(503) for _ in range(5)))

    async with client:
        with pytest.raises(SourceRequestError) as raised:
            await client.get(URL)

    assert len(stub.requests) == 3
    assert raised.value.attempts == 3
    assert raised.value.status_code == 503


async def test_gives_up_after_the_configured_attempts(harness: Harness) -> None:
    client, stub = harness.make(
        httpx.Response(503), httpx.Response(503), source_settings=settings(max_attempts=2)
    )

    async with client:
        with pytest.raises(SourceRequestError):
            await client.get(URL)

    assert len(stub.requests) == 2


@pytest.mark.parametrize(("jitter", "expected"), [(0.0, [0.5, 1.0]), (1.0, [1.0, 2.0])])
async def test_backs_off_exponentially_with_jitter(
    harness: Harness, jitter: float, expected: list[float]
) -> None:
    client, _ = harness.make(httpx.Response(503), httpx.Response(503), ok(), jitter=jitter)

    async with client:
        await client.get(URL)

    assert harness.clock.sleeps == expected


async def test_honours_retry_after_in_seconds(harness: Harness) -> None:
    client, stub = harness.make(httpx.Response(429, headers={"Retry-After": "7"}), ok())

    async with client:
        await client.get(URL)

    assert harness.clock.sleeps == [7.0]
    assert stub.request_times == [0.0, 7.0]


async def test_honours_retry_after_as_http_date(harness: Harness) -> None:
    retry_at = "Thu, 15 Oct 2026 12:00:30 GMT"  # START + 30 s
    client, _ = harness.make(httpx.Response(503, headers={"Retry-After": retry_at}), ok())

    async with client:
        await client.get(URL)

    assert harness.clock.sleeps == [30.0]


async def test_backoff_wins_when_retry_after_is_shorter(harness: Harness) -> None:
    client, _ = harness.make(
        httpx.Response(429, headers={"Retry-After": "0"}),
        ok(),
        source_settings=settings(backoff_base_seconds=4),
    )

    async with client:
        await client.get(URL)

    assert harness.clock.sleeps == [4.0]


async def test_fails_instead_of_waiting_for_an_excessive_retry_after(harness: Harness) -> None:
    client, stub = harness.make(httpx.Response(429, headers={"Retry-After": "3600"}), ok())

    async with client:
        with pytest.raises(SourceRequestError) as raised:
            await client.get(URL)

    assert len(stub.requests) == 1
    assert raised.value.status_code == 429
    assert harness.clock.sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 500, 301])
async def test_other_answers_fail_fast_without_retry(harness: Harness, status: int) -> None:
    client, stub = harness.make(httpx.Response(status), ok())

    async with client:
        with pytest.raises(SourceRequestError) as raised:
            await client.get(URL)

    assert len(stub.requests) == 1
    assert raised.value.attempts == 1
    assert raised.value.status_code == status


# --- source-specific "no data" -----------------------------------------------------------------


def ecb_no_results(response: httpx.Response) -> bool:
    return response.status_code == 404 and "No results found" in response.text


async def test_adapter_maps_its_no_data_answer_to_an_empty_delivery(harness: Harness) -> None:
    client, stub = harness.make(
        httpx.Response(404, text="No results found."), ok(), is_no_data=ecb_no_results
    )

    async with client:
        response = await client.get(URL)

    assert response.outcome is Outcome.NO_DATA
    assert response.status_code == 404
    assert len(stub.requests) == 1


async def test_other_404s_still_fail_when_the_adapter_maps_no_data(harness: Harness) -> None:
    client, stub = harness.make(httpx.Response(404, text="Not Found"), is_no_data=ecb_no_results)

    async with client:
        with pytest.raises(SourceRequestError):
            await client.get(URL)

    assert len(stub.requests) == 1


# --- conditional requests ----------------------------------------------------------------------


async def test_sends_conditional_request_headers(harness: Harness) -> None:
    client, stub = harness.make(ok())
    last_load = datetime(2026, 10, 15, 14, 30, tzinfo=timezone(timedelta(hours=2)))

    async with client:
        await client.get(URL, if_modified_since=last_load, if_none_match='"v42"')

    headers = stub.requests[0].headers
    assert headers["If-Modified-Since"] == "Thu, 15 Oct 2026 12:30:00 GMT"
    assert headers["If-None-Match"] == '"v42"'


async def test_unconditional_request_has_no_validators(harness: Harness) -> None:
    client, stub = harness.make(ok())

    async with client:
        await client.get(URL)

    assert "If-Modified-Since" not in stub.requests[0].headers
    assert "If-None-Match" not in stub.requests[0].headers


async def test_not_modified_is_reported_as_unchanged(harness: Harness) -> None:
    client, stub = harness.make(httpx.Response(304), ok())

    async with client:
        response = await client.get(URL, if_modified_since=START)

    assert response.outcome is Outcome.NOT_MODIFIED
    assert response.content == b""
    assert len(stub.requests) == 1


async def test_rejects_a_naive_if_modified_since(harness: Harness) -> None:
    client, stub = harness.make(ok())

    async with client:
        with pytest.raises(ValueError, match="timezone-aware"):
            await client.get(URL, if_modified_since=datetime(2026, 10, 15))

    assert stub.requests == []


# --- kill switch -------------------------------------------------------------------------------


async def test_disabled_source_sends_no_request(harness: Harness) -> None:
    client, stub = harness.make(ok(), source_settings=settings(enabled=False))

    async with client:
        with pytest.raises(SourceDisabledError):
            await client.get(URL)

    assert stub.requests == []
    assert harness.request_counts() == {}


# --- metric ------------------------------------------------------------------------------------


async def test_counts_every_attempt_by_source_and_status(harness: Harness) -> None:
    client, _ = harness.make(
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("refused"),
        httpx.Response(503),
        source_settings=settings(max_attempts=3),
    )
    second, _ = harness.make(httpx.Response(304), ok())

    async with client, second:
        with pytest.raises(SourceRequestError):
            await client.get(URL)
        await second.get(URL)
        await second.get(URL)

    assert harness.request_counts() == {
        ("ecb", "timeout"): 1,
        ("ecb", "network_error"): 1,
        ("ecb", "503"): 1,
        ("ecb", "304"): 1,
        ("ecb", "200"): 1,
    }
