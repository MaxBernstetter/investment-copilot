# Access Service

The `access` service (`src/services/access/`) is the public, read-only API of YieldLens. It is the only service the frontend calls. It serves one curve as of a knowledge time and relays persistence readiness.

## Interface (`api` process)

| Method and path | Purpose | Responses |
|---|---|---|
| `GET /v1/curves/{curve_id}/observations?valid_date=&as_of=` | One curve on one valid date, as it was known at `meta.as_of` (both query parameters optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/maturities/{maturity}/observations?from=&to=&as_of=` | One maturity of a curve over valid dates, as it was known at `meta.as_of`: points in valid-date order, dates without a published value known then left out (all query parameters optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/maturities/{maturity}/observations/{valid_date}/versions?as_of=` | The version history of one value, as it was known at `meta.as_of`: versions oldest first, with `known_to` null while current; versions first known after `as_of` left out (`as_of` optional) | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /v1/curves/{curve_id}/changes?from=&to=&since=&as_of=` | What changed in a curve over valid dates (`from`, `to` inclusive) between the knowledge times `meta.since` and `meta.as_of`: a value changed, or known only at `as_of` (`old_value` null); `since` is required, `as_of` optional | `200` envelope `{data, meta}` with `ETag`; `304` when `If-None-Match` matches; errors below |
| `GET /health` | Liveness: the process is up | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: the persistence service answers `200` on its own `/ready` | `200 {"status": "ready"}`, `503 {"status": "unavailable"}` (also when persistence is unreachable) |

- `curve_id`: 1 to 64 characters. `valid_date`: ISO date. `as_of`: timezone-aware ISO datetime; a naive one is rejected.
- `data` holds `curve_id`, `valid_date` and `points` in grid order (`maturity`, `months`, `value`); a maturity with no published value known as of `meta.as_of` has `value: null`.
- `meta.as_of` is the knowledge time used, in UTC. Without `as_of` persistence picks the database clock and the answer echoes it.
- Only `GET` is allowed (`405` otherwise).
- CORS: only `GET` is allowed, from the origins in `ACCESS_CORS_ORIGINS`. Other origins get no `Access-Control-Allow-Origin` header.

### Caching

- All data endpoints return an `ETag` for the exact response body: a quoted digest of the body, so the same answer always carries the same tag.
- A settled answer is immutable: when the request has an `as_of` and `meta.as_of` equals it (as instants, so any UTC offset matches), both send `Cache-Control: public, max-age=31536000, immutable`. The answer never changes, so caches may reuse it without asking.
- Every other answer sends `Cache-Control: no-cache`: no `as_of` was requested, or persistence answered at its knowledge horizon because the requested `as_of` was later. Caches must revalidate with the `ETag` before reuse.
- A `304` carries the same `Cache-Control` as the `200` it stands for.
- Conditional GET: a request with `If-None-Match` that lists the current tag (or `*`) gets `304 Not Modified` with the `ETag` and no body. Lists of tags and weak (`W/`) tags are accepted. Any other tag gets the full `200`.
- Errors (problem details) carry no `ETag` and no `Cache-Control`; they are never cached by this rule.

### Errors

All errors are RFC 9457 problem details (`application/problem+json`).

| Status | Title | When | Source |
|---|---|---|---|
| `404` | Not found | The curve is unknown | Persistence `404`, detail passed through |
| `422` | Invalid request | Malformed parameters (before persistence is called), or persistence rejects the query | Own validation, or persistence `422` with its detail |
| `503` | Service unavailable | Persistence is unreachable, times out, answers `5xx` or sends an unexpected body | Transport errors and other statuses |

The OpenAPI document is generated from the app (`task access:openapi`) and published at `src/contracts/openapi/access/v1.json`; a unit test fails when it is stale.

## Layers

| Package | Content |
|---|---|
| `access.domain` | `CurveAsOf` and `CurvePoint`, the version history and changes of values, and the errors of reading a curve |
| `access.application` | `CurveReader` port |
| `access.infrastructure` | `PersistenceClient`: readiness, and the curve read (maps persistence answers and errors to the domain) |
| `access.facade` | FastAPI app, CORS, routes, problem handlers, mapping to `contracts.access.v1`, OpenAPI export |
| `access.api` | Composition root of the `api` process |

import-linter enforces that dependencies point inward and that domain and application import no frameworks, HTTP clients or contracts.

## Configuration

Environment variables, validated at startup (pydantic-settings):

| Variable | Default | Meaning |
|---|---|---|
| `ACCESS_PERSISTENCE_URL` | – (required) | Base URL of the persistence api, e.g. `http://localhost:8001` |
| `ACCESS_PERSISTENCE_TIMEOUT_SECONDS` | `10` | Timeout of one call to persistence |
| `ACCESS_CORS_ORIGINS` | `http://localhost:5174` | Comma-separated origins allowed to call the API (the Vite dev server by default) |

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
- Other read endpoints (only the curve endpoint exists)
- Transparency (lineage and run status for the frontend)
- Metrics
- Traces
