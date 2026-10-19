# Interfaces and Contracts

## Contracts package

- `contracts/` is the **only** code shared between services. It contains Pydantic interface models and the OpenAPI document per service, versioned as the Python package `contracts.<service>.v<N>` (`src/contracts/src/contracts/<service>/v<N>/`). `src/contracts` is its own uv project; services depend on it by path.
- Contracts contain data shapes and validation only, with no behaviour.
- Breaking change → new major version. Old versions stay until no consumer uses them.
- The frontend consumes the `access` OpenAPI document through a generated TypeScript client. The document is generated from the app by `task access:openapi` and published at `src/contracts/openapi/access/v1.json`; the unit test `test_published_openapi_document_is_current` fails when the code and the published file drift.

## Dependency rules

| Rule | Enforcement |
|---|---|
| A service never imports another service | Separate uv projects; import-linter in CI |
| A service may import only `contracts` from the monorepo | Path dependency; import-linter |
| A service never reads another service's schema | One DB user per schema, no cross-schema grants |
| A service never calls another service's internal endpoints | Only documented OpenAPI endpoints; contract tests |

## REST standards

- **Contract-first:** the OpenAPI document is the source of truth. Implementations are tested against it.
- **Resources and naming:** plural nouns, kebab-case paths, snake_case JSON fields, e.g. `GET /v1/curves/{curve_id}/observations?valid_date=2026-03-12`.
- **Versioning:** major version in the URI (`/v1`). Additive changes stay within the version.
- **Time:** ISO-8601 throughout, UTC timestamps. Every data endpoint accepts `as_of` (knowledge time). If it is omitted, the latest known state is returned and the effective `as_of` is echoed in the response.
- **Envelope:** data responses carry `data` and `meta` (`as_of`, version ids, quality status incl. `warning` flags from validation gates, lineage refs). Data quarantined by a blocking gate is not returned.
- **Pagination:** cursor-based (`limit`, `cursor`, `next_cursor`).
- **Errors:** RFC 9457 problem details (`application/problem+json`).
- **Caching:**
  - Every response carries an `ETag`; conditional GET (`If-None-Match`) answers `304` without a body.
  - A settled answer is immutable: the request had an `as_of` and the response's `meta.as_of` equals it. It gets `Cache-Control: public, max-age=31536000, immutable`.
  - Every other answer gets `Cache-Control: no-cache` (revalidate with the `ETag`). Persistence answers an `as_of` after its knowledge horizon at the horizon, so such an answer is not settled.
  - Errors are not cached by this rule.
- **Writes:**
  - `POST` with an `Idempotency-Key` header, so retries from Airflow are safe.
  - Long-running operations (backfill, recalculation) return `202 Accepted` plus a run resource to poll.
- **Operations:** every service exposes `/health` (liveness) and `/ready` (readiness), used by Compose health checks, and propagates W3C `traceparent` on every call.
- **Security:**
  - The public interface (`access`) is read-only, rate-limited, with CORS restricted to the frontend origin.
  - Write and admin endpoints exist only on internal services, which are not exposed publicly.

## Bulk interfaces

JSON pages don't scale for history-wide reads (recalculation, mart rebuilds). For bulk transfer between services:

- Streamed **Apache Arrow IPC** endpoints (`Accept: application/vnd.apache.arrow.stream`), chunked by valid-date range.
- Same resource paths and `as_of` semantics as the JSON endpoints.
- Callers parallelize by chunk, which is driven by Airflow task mapping (see [[04-orchestration]]).

## Transparency interface

Every domain service implements the common contract `contracts/transparency/v1` next to its domain interface:
- `GET /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/lineage/{ref}`
- `GET /v1/alerts`

Each service serves only its own data. Lineage entries carry upstream refs (service + ref) so that `access` can assemble cross-service lineage. Telemetry (metrics, logs, traces) is not part of the REST interface; it follows [[10-observability]].
