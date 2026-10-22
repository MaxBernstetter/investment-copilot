# Access Service

The `access` service (`src/services/access/`) is the public, read-only API of YieldLens. It is the only service the frontend calls. It serves one curve as of a knowledge time and relays persistence readiness.

## Interface (`api` process)

| Method and path | Purpose | Responses |
|---|---|---|
| `GET /v1/curves` | The curve catalogue: every curve with `curve_id`, `label`, `source_id`, `area`, `attribution`, `rate_type`, `compounding`, `unit`, `source_model`, `simulated` and its grid `maturities` (`maturity`, `months`, shortest first), ordered by `curve_id` | `200` `{data}` with `ETag` and `Cache-Control: public, max-age=300`; `304` when `If-None-Match` matches; `503` |
| `GET /v1/curves/{curve_id}/observations?valid_date=&as_of=` | One curve on one valid date, as it was known at `meta.as_of` (both query parameters optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/maturities/{maturity}/observations?from=&to=&as_of=` | One maturity of a curve over valid dates, as it was known at `meta.as_of`: points in valid-date order, dates without a published value known then left out (all query parameters optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/maturities/{maturity}/observations/{valid_date}/versions?as_of=` | The version history of one value, as it was known at `meta.as_of`: versions oldest first, with `known_to` null while current; versions first known after `as_of` left out (`as_of` optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/changes?from=&to=&since=&as_of=` | What changed in a curve over valid dates (`from`, `to` inclusive) between the knowledge times `meta.since` and `meta.as_of`: a value changed, or known only at `as_of` (`old_value` null); `since` is required, `as_of` optional | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/quality?from=&to=&as_of=` | Quality of each TARGET business day of a curve over valid dates (`from`, `to` inclusive), as known at `meta.as_of` (`from` and `to` required; `as_of` optional) | `200` envelope `{data, meta}` with `ETag` and `Cache-Control: no-cache`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/measures?from=&to=&as_of=` | Derived measures per valid date (spreads, curvature and inversion), as known at `meta.as_of` (`from` and `to` required; `as_of` optional); relayed from processing, see [[04-derived-measures]] | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /health` | Liveness: the process is up | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: the persistence service answers `200` on its own `/ready` | `200 {"status": "ready"}`, `503 {"status": "unavailable"}` (also when persistence is unreachable) |

- `curve_id`: 1 to 64 characters. `valid_date`: ISO date. `as_of`: timezone-aware ISO datetime; a naive one is rejected.
- `data` holds `curve_id`, `valid_date` and `points` in grid order (`maturity`, `months`, `value`, `version_id`, `origin`, `quality`); a maturity with no published value known as of `meta.as_of` has `value: null`, `version_id: null` and `quality: null`.
- Series points carry `version_id`, `origin` and `quality` too. `version_id` is the lineage reference of the visible version: it is the id the versions endpoint lists for that value. `origin` is `published` for every value the service returns: values are passed on unmodified. `quality` carries the processing status (`passed`, `info`, `warn`, or `unchecked`) and any rule flags with explanations.
- Curve and series answers call the processing service (`GET /v1/curves/{curve_id}/value-quality`) for the visible values and attach the result. When processing is unavailable, values are `unchecked` and the answer is not cached as immutable.
- The measures endpoint relays processing (`GET /v1/curves/{curve_id}/measures`): each valid date carries the spreads, curvature and inversion with their inputs (value, `version_id`, `status`), the inputs missing, and the worst input quality. `meta.method_version` identifies the measure definitions and the input set; measures are computed on read, never stored.
- The quality endpoint relays processing (`GET /v1/curves/{curve_id}/quality`) per TARGET business day: each day lists overall status, per-rule outcomes and findings (rule, severity, maturity, explanation, evidence). Answers always send `Cache-Control: no-cache` even when `as_of` is settled.
- `meta.as_of` is the knowledge time used, in UTC. Without `as_of` persistence picks the database clock and the answer echoes it.
- `meta.source_attribution` is required on the curve, series, versions, changes, quality and measures answers. It comes from the curve catalogue owned by persistence (`GET /v1/curves` there), so `ecb-aaa-spot` carries `Source: ECB statistics` (ESCB reuse terms) and `ecb-aaa-spot-sim` carries `Simulated scenario based on ECB statistics`, as the catalogue states them. Access reuses the catalogue for `ACCESS_CATALOGUE_TTL_SECONDS` per process, so a new curve appears within one TTL. A curve that is not in the catalogue is answered `404` before persistence or processing is called, never without attribution. If a refresh of the catalogue fails after one was loaded, the last loaded catalogue is served and the refresh is retried on the next request; `503` only when no catalogue was ever loaded.
- Only `GET` is allowed (`405` otherwise).
- CORS: only `GET` is allowed, from the origins in `ACCESS_CORS_ORIGINS`. Other origins get no `Access-Control-Allow-Origin` header.

### Caching

- All data endpoints return an `ETag` for the exact response body: a quoted digest of the body, so the same answer always carries the same tag.
- A settled answer is immutable: when the request has an `as_of` and `meta.as_of` equals it (as instants, so any UTC offset matches), and every published value has a known quality result that is not `unchecked`, both send `Cache-Control: public, max-age=31536000, immutable`. The answer never changes, so caches may reuse it without asking. An answer with an unchecked value is not settled.
- Every other answer sends `Cache-Control: no-cache`: no `as_of` was requested, or persistence answered at its knowledge horizon because the requested `as_of` was later. Caches must revalidate with the `ETag` before reuse.
- A measures answer is settled when `as_of` is requested and echoed, and every input of every point has a quality result that is not `unchecked`; otherwise it is `no-cache`.
- A `304` carries the same `Cache-Control` as the `200` it stands for.
- Conditional GET: a request with `If-None-Match` that lists the current tag (or `*`) gets `304 Not Modified` with the `ETag` and no body. Lists of tags and weak (`W/`) tags are accepted. Any other tag gets the full `200`.
- Errors (problem details) carry no `ETag` and no `Cache-Control`; they are never cached by this rule.
- The curve catalogue is reference data, not bitemporal: `GET /v1/curves` sends `Cache-Control: public, max-age=300` with an `ETag`. Access also keeps it in process for `ACCESS_CATALOGUE_TTL_SECONDS`, so one catalogue read serves many requests.

### Errors

All errors are RFC 9457 problem details (`application/problem+json`).

| Status | Title | When | Source |
|---|---|---|---|
| `404` | Not found | The curve is unknown | The curve catalogue (detail `no curve named …`); persistence (or processing, for the quality and measures endpoints) `404`, detail passed through |
| `422` | Invalid request | Malformed parameters (before persistence is called), or persistence rejects the query | Own validation, or persistence (or processing, for the quality and measures endpoints) `422` with its detail |
| `503` | Service unavailable | Persistence is unreachable, times out, answers `5xx` or sends an unexpected body, or the catalogue cannot be read; or the quality endpoint cannot reach processing; or the measures endpoint cannot reach processing | Transport errors and other statuses; quality reads use detail *The quality service is not reachable; try again later.*; measures reads use detail *The measures service is not reachable; try again later.* |
| `500` | Internal server error | Any unexpected error | Own; generic detail, `trace_id` when traced |

A `500` raised by an unexpected error skips the CORS middleware, so browsers cannot read its body; the frontend shows its generic error.

The OpenAPI document is generated from the app (`task access:openapi`) and published at `src/contracts/openapi/access/v1.json`; a unit test fails when it is stale.

## Layers

| Package | Content |
|---|---|
| `access.domain` | `CurveAsOf` and `CurvePoint`, the curve catalogue entries, the version history and changes of values, the derived measures, and the errors of reading a curve |
| `access.application` | `CurveReader` and `CatalogueReader` ports; `CachedCatalogue` (TTL cache of the catalogue) |
| `access.infrastructure` | `PersistenceClient` and `ProcessingClient`: readiness, the catalogue and curve reads from persistence; value quality, per-day quality and derived measures from processing |
| `access.facade` | FastAPI app, CORS, routes, problem handlers, mapping to `contracts.access.v1`, OpenAPI export |
| `access.api` | Composition root of the `api` process |

import-linter enforces that dependencies point inward and that domain and application import no frameworks, HTTP clients or contracts.

## Configuration

Environment variables, validated at startup (pydantic-settings):

| Variable | Default | Meaning |
|---|---|---|
| `ACCESS_PERSISTENCE_URL` | – (required) | Base URL of the persistence api, e.g. `http://localhost:8001` |
| `ACCESS_PERSISTENCE_TIMEOUT_SECONDS` | `10` | Timeout of one call to persistence |
| `ACCESS_PROCESSING_URL` | – (required) | Base URL of the processing api, e.g. `http://localhost:8002` |
| `ACCESS_PROCESSING_TIMEOUT_SECONDS` | `5` | Timeout of one call to processing |
| `ACCESS_CATALOGUE_TTL_SECONDS` | `300` | Seconds the curve catalogue is reused before it is read from persistence again |
| `ACCESS_CORS_ORIGINS` | `http://localhost:5174` | Comma-separated origins allowed to call the API (the Vite dev server by default). Live: `https://maxbernstetter.github.io` (the Pages origin only), set on the VM (#182) |

## Running locally

```sh
devbox run -- task access:setup     # virtual environment
devbox run -- task persistence:run  # persistence api on http://localhost:8001 (for readiness)
devbox run -- task access:run       # access api on http://localhost:8000
```

`PORT` changes the port of `access:run`. Logs are JSON lines (`log_config.json`).

## Tests

- `devbox run -- task access:test:unit`: REST routes and problem responses, CORS, the persistence client (with `httpx.MockTransport`), the OpenAPI drift check, configuration and the log configuration. No network.
- `devbox run -- task access:openapi`: regenerates `src/contracts/openapi/access/v1.json`; run it after changing the interface.
- `devbox run -- task access:lint`, `access:typecheck`: ruff, import-linter, mypy (strict).

## Not yet in place

- Rate limiting
- Other read endpoints beyond the catalogue, curves, series, versions, changes, quality and measures
- Run status and alerts (#139)
- Metrics
- Traces
