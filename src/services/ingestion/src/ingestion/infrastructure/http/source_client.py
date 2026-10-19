"""Polite HTTP client for public data sources.

Every call to a source goes through one ``SourceClient`` per source. It enforces the
source access policy (``docs/architecture/12-data-pipeline.md``): a concurrency limit
and a minimum interval between requests, a timeout, bounded retries with exponential
backoff and jitter, ``Retry-After``, conditional requests, a kill switch, the YieldLens
``User-Agent`` and the request counter ``yl_ingestion_source_requests_total``.

The limits hold per client instance, that is per process. Limits across processes are
the orchestrator's job (an Airflow pool of size 1 per source).
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from enum import StrEnum
from importlib.metadata import version
from types import TracebackType
from typing import Protocol, Self

import httpx
from opentelemetry import metrics

from ingestion.config import SourceSettings

logger = logging.getLogger(__name__)

REPOSITORY_URL = "https://github.com/MaxBernstetter/yield-lens"
USER_AGENT = f"YieldLens/{version('ingestion')} (+{REPOSITORY_URL})"
REQUESTS_METRIC = "yl_ingestion_source_requests_total"

RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


class Outcome(StrEnum):
    """What a successful call to a source delivered."""

    DELIVERED = "delivered"
    """``2xx``: the payload is in ``SourceResponse.content``."""
    NOT_MODIFIED = "not_modified"
    """``304``: unchanged since the conditional request's validators."""
    NO_DATA = "no_data"
    """The source's "no data" answer, as recognised by the adapter: an empty delivery."""


@dataclass(frozen=True)
class SourceResponse:
    outcome: Outcome
    status_code: int
    content: bytes
    headers: httpx.Headers
    """Response headers, e.g. ``Last-Modified`` and ``ETag`` as delivery metadata."""
    url: str
    """The full request URL, query string included."""
    fetched_at: datetime
    """When the answer arrived (UTC, from the client's clock)."""


class SourceDisabledError(Exception):
    """The source is switched off by configuration (kill switch). No request was sent."""

    def __init__(self, source: str) -> None:
        super().__init__(f"source {source!r} is disabled by configuration")
        self.source = source


class SourceRequestError(Exception):
    """The request failed: a non-retryable answer, or retries were exhausted."""

    def __init__(self, source: str, url: str, attempts: int, status_code: int | None) -> None:
        answer = f"status {status_code}" if status_code is not None else "no response"
        super().__init__(
            f"request to source {source!r} failed after {attempts} attempt(s), {answer}: {url}"
        )
        self.source = source
        self.url = url
        self.attempts = attempts
        self.status_code = status_code
        """``None`` when no HTTP answer was received (network error or timeout)."""


class Clock(Protocol):
    """Time source. Injected so that pacing and backoff are testable without waiting."""

    def monotonic(self) -> float: ...

    def now(self) -> datetime: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


NoDataPredicate = Callable[[httpx.Response], bool]


def never_no_data(_response: httpx.Response) -> bool:
    return False


@dataclass(frozen=True)
class _Failure:
    status_code: int | None
    is_retryable: bool
    retry_after_seconds: float | None = None


class SourceClient:
    """HTTP client for one source. Use as an async context manager.

    ``is_no_data`` lets the source adapter recognise the source's "no data" answer
    (e.g. the ECB's ``404`` "No results found"); such a response is returned as
    ``Outcome.NO_DATA`` and never retried.
    """

    def __init__(
        self,
        source: str,
        settings: SourceSettings,
        *,
        is_no_data: NoDataPredicate = never_no_data,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Clock | None = None,
        jitter: Callable[[], float] = random.random,
        meter: metrics.Meter | None = None,
    ) -> None:
        self._source = source
        self._settings = settings
        self._is_no_data = is_no_data
        self._clock = clock or SystemClock()
        self._jitter = jitter
        self._http = httpx.AsyncClient(
            transport=transport,
            timeout=settings.timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        self._slots = asyncio.Semaphore(settings.max_concurrent_requests)
        self._pacing = asyncio.Lock()
        self._next_start = float("-inf")
        self._requests = (meter or metrics.get_meter("ingestion")).create_counter(
            REQUESTS_METRIC,
            unit="1",
            description="Requests (attempts) sent to a source, by source and HTTP status",
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        if_modified_since: datetime | None = None,
        if_none_match: str | None = None,
    ) -> SourceResponse:
        """GET ``url`` politely.

        Raises ``SourceDisabledError`` if the kill switch is on, and
        ``SourceRequestError`` on a non-retryable answer or when retries are exhausted.
        """
        if not self._settings.enabled:
            raise SourceDisabledError(self._source)
        headers = _conditional_headers(if_modified_since, if_none_match)
        attempt = 0
        while True:
            attempt += 1
            result = await self._attempt(url, params, headers)
            if isinstance(result, SourceResponse):
                return result
            delay = self._retry_delay(attempt, result)
            if delay is None:
                raise SourceRequestError(self._source, url, attempt, result.status_code)
            logger.warning(
                "retrying source request in %.1f s",
                delay,
                extra={
                    "source": self._source,
                    "status_code": result.status_code,
                    "attempt": attempt,
                },
            )
            await self._clock.sleep(delay)

    async def _attempt(
        self, url: str, params: Mapping[str, str] | None, headers: Mapping[str, str]
    ) -> SourceResponse | _Failure:
        async with self._slots:
            await self._wait_for_turn()
            try:
                response = await self._http.get(url, params=params, headers=headers)
            except httpx.TimeoutException:
                self._count("timeout")
                return _Failure(status_code=None, is_retryable=True)
            except httpx.TransportError:
                self._count("network_error")
                return _Failure(status_code=None, is_retryable=True)
        self._count(str(response.status_code))
        return self._classify(response)

    async def _wait_for_turn(self) -> None:
        async with self._pacing:
            delay = self._next_start - self._clock.monotonic()
            if delay > 0:
                await self._clock.sleep(delay)
            self._next_start = self._clock.monotonic() + self._settings.min_interval_seconds

    def _classify(self, response: httpx.Response) -> SourceResponse | _Failure:
        if self._is_no_data(response):
            return self._response(Outcome.NO_DATA, response)
        if response.status_code == httpx.codes.NOT_MODIFIED:
            return self._response(Outcome.NOT_MODIFIED, response)
        if response.is_success:
            return self._response(Outcome.DELIVERED, response)
        if response.status_code in RETRYABLE_STATUS_CODES:
            retry_after = _retry_after_seconds(response, self._clock.now())
            return _Failure(
                response.status_code, is_retryable=True, retry_after_seconds=retry_after
            )
        return _Failure(response.status_code, is_retryable=False)

    def _retry_delay(self, attempt: int, failure: _Failure) -> float | None:
        """Seconds to wait before the next attempt, or ``None`` if there is none."""
        if not failure.is_retryable or attempt >= self._settings.max_attempts:
            return None
        backoff = self._settings.backoff_base_seconds * 2.0 ** (attempt - 1)
        delay = backoff / 2 + self._jitter() * backoff / 2
        if failure.retry_after_seconds is None:
            return delay
        if failure.retry_after_seconds > self._settings.max_retry_after_seconds:
            return None
        return max(delay, failure.retry_after_seconds)

    def _response(self, outcome: Outcome, response: httpx.Response) -> SourceResponse:
        return SourceResponse(
            outcome,
            response.status_code,
            response.content,
            response.headers,
            str(response.url),
            self._clock.now(),
        )

    def _count(self, status: str) -> None:
        self._requests.add(1, {"source": self._source, "status": status})


def _conditional_headers(
    if_modified_since: datetime | None, if_none_match: str | None
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if if_modified_since is not None:
        if if_modified_since.tzinfo is None:
            raise ValueError("if_modified_since must be timezone-aware")
        headers["If-Modified-Since"] = format_datetime(
            if_modified_since.astimezone(UTC), usegmt=True
        )
    if if_none_match is not None:
        headers["If-None-Match"] = if_none_match
    return headers


def _retry_after_seconds(response: httpx.Response, now: datetime) -> float | None:
    """Parse ``Retry-After`` (delay seconds or HTTP date); ``None`` if absent or invalid."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        return None
    return max(0.0, (moment - now).total_seconds())
