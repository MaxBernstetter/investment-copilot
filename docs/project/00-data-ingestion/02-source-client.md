# Source Client

The HTTP client every source adapter uses to call a public source. It enforces the [[12-data-pipeline#Source access policy]] in one place, so ingestion cannot get YieldLens rate-limited or banned. The values per source are in its source note (ECB: [[01-data-sources#Access policy for this source]]).

Tracked in [#66](https://github.com/MaxBernstetter/investment-copilot/issues/66). Code: `src/services/ingestion/src/ingestion/infrastructure/http/source_client.py`.

## What it does

| Rule | Behaviour |
|---|---|
| Kill switch | `enabled=false` raises `SourceDisabledError` before any request is sent |
| Concurrency | At most `max_concurrent_requests` requests in flight per client |
| Pacing | At least `min_interval_seconds` between the starts of two requests, retries included |
| Timeout | `timeout_seconds` per request (connect, read, write, pool) |
| Retries | Only on network errors, timeouts, `429`, `502`, `503`, `504`; at most `max_attempts` (≤ 3) attempts per request |
| Backoff | Before retry *n*: `backoff_base_seconds × 2^(n−1)`, with jitter in the upper half (50–100 % of that value) |
| `Retry-After` | Honoured, as seconds or as HTTP date: the client waits for the longer of `Retry-After` and the backoff. A `Retry-After` above `max_retry_after_seconds` is not waited for: the request fails at once |
| Fail fast | Any other answer (`4xx`, `500`, redirects) raises `SourceRequestError` without retry |
| "No data" | The adapter passes a predicate `is_no_data(response)`. A matching response is an empty delivery (`Outcome.NO_DATA`), checked first and never retried |
| Conditional requests | `if_modified_since` (timezone-aware) and `if_none_match` become `If-Modified-Since` / `If-None-Match`. `304` is `Outcome.NOT_MODIFIED` |
| Identification | `User-Agent: YieldLens/<version> (+https://github.com/MaxBernstetter/investment-copilot)`; the version is the `ingestion` package version. No personal contact data |
| Metric | Every attempt counts once in `yl_ingestion_source_requests_total{source,status}` |

The limits hold **per client instance**, that is per process. Use one client per source and process. Limits across processes are the orchestrator's job: an Airflow pool of size 1 per source ([#21](https://github.com/MaxBernstetter/investment-copilot/issues/21), [#27](https://github.com/MaxBernstetter/investment-copilot/issues/27)).

## Interface

```python
from ingestion.config import IngestionSettings
from ingestion.infrastructure.http import Outcome, SourceClient

settings = IngestionSettings()  # once at startup; fails on invalid or unknown variables

async with SourceClient(
    "ecb", settings.sources.ecb, is_no_data=ecb_no_results
) as client:
    response = await client.get(url, params={...}, if_modified_since=last_modified)

match response.outcome:
    case Outcome.DELIVERED:
        ...  # response.content, response.headers (Last-Modified, ETag)
    case Outcome.NOT_MODIFIED:
        ...  # no-op run
    case Outcome.NO_DATA:
        ...  # successful run with zero rows
```

| Name | Meaning |
|---|---|
| `SourceClient(source, settings, *, is_no_data, transport, clock, jitter, meter)` | `source` is the metric label. `transport`, `clock`, `jitter` and `meter` are injected for tests; the defaults are the real ones |
| `SourceClient.get(url, *, params, if_modified_since, if_none_match) -> SourceResponse` | One polite GET, retries included |
| `SourceResponse(outcome, status_code, content, headers)` | The answer; `headers` keep delivery metadata for the raw layer |
| `Outcome` | `DELIVERED`, `NOT_MODIFIED`, `NO_DATA` |
| `SourceDisabledError` | The kill switch is on; nothing was sent |
| `SourceRequestError(source, url, attempts, status_code)` | Non-retryable answer or retries exhausted; `status_code` is `None` after a network error or timeout |

The ECB adapter ([#14](https://github.com/MaxBernstetter/investment-copilot/issues/14), [[03-ecb-load]]) passes `ingestion.infrastructure.ecb.is_no_data`: a `404` whose body says "No Series was returned" or "No results found".

## Configuration

Environment variables, validated at startup with pydantic-settings. Naming scheme: `INGESTION_SOURCES__<SOURCE>__<SETTING>`. Unknown sources and settings are rejected, so a typo fails at startup. The defaults are the ECB values.

| Variable (ECB) | Default | Rule |
|---|---|---|
| `INGESTION_SOURCES__ECB__ENABLED` | `true` | Kill switch |
| `INGESTION_SOURCES__ECB__MAX_CONCURRENT_REQUESTS` | `1` | ≥ 1 |
| `INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS` | `2` | ≥ 0 |
| `INGESTION_SOURCES__ECB__TIMEOUT_SECONDS` | `60` | > 0 |
| `INGESTION_SOURCES__ECB__MAX_ATTEMPTS` | `3` | 1–3 (policy cap) |
| `INGESTION_SOURCES__ECB__BACKOFF_BASE_SECONDS` | `1` | > 0 |
| `INGESTION_SOURCES__ECB__MAX_RETRY_AFTER_SECONDS` | `120` | ≥ 0 |

A new source adds one field to `SourcesSettings` in `ingestion/config.py`, which adds its `INGESTION_SOURCES__<SOURCE>__*` variables.

## Metric

| Metric | Labels | Meaning |
|---|---|---|
| `yl_ingestion_source_requests_total` | `source` (e.g. `ecb`), `status` (HTTP status code such as `200`, `304`, `429`, or `timeout`, `network_error`) | Requests sent to a source, one per attempt. A rising `429`/`503` share shows throttling before it becomes a ban |

It is recorded through the OpenTelemetry metrics API. Without a configured SDK it is a no-op; the exporter setup comes with the observability platform.

## Tests

`src/services/ingestion/tests/unit/infrastructure/http/test_source_client.py` runs the client against `httpx.MockTransport` and a fake clock, so pacing and backoff are checked without waiting and **no test calls a live source**. The metric is read with the OpenTelemetry SDK's in-memory reader.

```
devbox run -- task ingestion:test:unit
```
