# Persistence Service

The `persistence` service (`src/services/persistence/`) owns the `CORE` schema and exposes the bitemporal store through REST. Data model: [[01-bitemporal-model]]. Design rules: [[11-service-design]].

## Interface (`api` process)

The contract is `contracts.persistence.v1` (`src/contracts/src/contracts/persistence/v1/`).

| Method and path | Purpose | Responses |
|---|---|---|
| `POST /v1/observations/versions` | Record a batch of observations as versions, all or nothing; unchanged observations are no-ops | `200` `RecordVersionsResponse`; `409` a concurrent write recorded the first version of an observation of the batch first (retry); `422` contract violation, an observation appears twice in the batch, or it names an undefined curve or a maturity off its curve's grid |
| `GET /v1/curves/{curve_id}/observations` | One published curve on one valid date as it was known at `as_of`; every grid maturity in grid order, `value` null where no published value was known | `200` `CurveObservationsResponse`; `404` no published value of the curve is known as of the time (or the curve is undefined); `422` invalid request, a naive `as_of`, or `as_of` after the database clock |
| `GET /v1/curves/{curve_id}/maturities/{maturity}/observations` | One published maturity of a curve over a range of valid dates as it was known at `as_of`; points in valid-date order, valid dates without a visible published value left out (gaps) | `200` `SeriesObservationsResponse`; `404` the maturity is not on the curve's grid (or the curve is undefined), or no published value is known in the range as of the time; `422` invalid request, `from` after `to`, a range longer than 3660 days, a naive `as_of`, or `as_of` after the database clock |
| `GET /health` | Liveness | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: the database answers a ping | `200 {"status": "ready"}`, `503 {"status": "unavailable"}` |

- Request `RecordVersionsRequest`: `observations`, a list of 1 to 10 000 `ObservationVersion` (`curve_id`, `maturity`, `valid_date`, `value`, `origin`, `method_version`, `source_id`, `run_id`, `change_reason`, optional `normalization_version`, optional `delivery_id`). Larger loads are split into chunks by the caller.
- Response `RecordVersionsResponse`: `recorded_count`, the number of new versions (new or changed observations); `unchanged_count`, the observations whose open version already had the same value and source (nothing stored); and `known_from`, the knowledge time (UTC) of the call, which all its new versions share. `recorded_count + unchanged_count` is the batch size.
- Versioning: a changed `value` or `source_id` closes the open version and opens a new one; resending an unchanged observation (also from another run) is an idempotent no-op that returns `200`. See [[01-bitemporal-model#Versioning]].
- Errors are RFC 9457 problem details (`application/problem+json`).
- Knowledge time can't be set through the API; only the database clock sets it.

### Reading a curve as of a time

`GET /v1/curves/{curve_id}/observations` takes two optional query parameters:

- `as_of` (timezone-aware, e.g. `2026-03-13T08:00:00Z`): the knowledge time to read at. Defaults to the database clock (UTC), which is echoed in `meta.as_of`. A time after the database clock is `422`.
- `valid_date` (`YYYY-MM-DD`): the valid date of the curve. Defaults to the latest valid date with a published value known at `as_of`.

The response `CurveObservationsResponse` carries `data` (`curve_id`, `valid_date`, `points` in grid order with `maturity`, `months` and `value`; `value` is null for a maturity with no published value known at `as_of`) and `meta.as_of`. Only published values count, and a version is visible when `known_from <= as_of < known_to`, so a past `as_of` gives the same answer after later revisions. See [[01-bitemporal-model#As-of retrieval]].

### Reading a maturity over time

`GET /v1/curves/{curve_id}/maturities/{maturity}/observations` reads one maturity as a series. Query parameters, all optional:

- `from` and `to` (`YYYY-MM-DD`): the inclusive valid-date range. `to` defaults to the latest valid date with a published value known at `as_of`; `from` defaults to 365 days before `to`. `from` after `to`, or a range longer than 3660 days, is `422`.
- `as_of` (timezone-aware): the knowledge time to read at, as for the curve. Defaults to the database clock.

The response `SeriesObservationsResponse` carries `data` (`curve_id`, `maturity`, `points` with `valid_date` and `value`, in valid-date order) and `meta.as_of`. A valid date without a visible published value has no point, so the series has gaps rather than null values. See [[01-bitemporal-model#As-of retrieval]].

## Layers

| Package | Content |
|---|---|
| `persistence.domain` | `Observation`, `ObservationKey`, `RecordedVersions`, the rule that a batch names each observation once; `CurveAsOf` and `CurvePoint`; `Series` and `SeriesPoint`; domain errors |
| `persistence.application` | `RecordVersions`, `GetCurveAsOf` and `GetSeriesAsOf` use cases and their ports (`ObservationRepository`, `CurveReader`, `SeriesReader`) |
| `persistence.infrastructure` | `OracleObservationRepository`: calls `core.core_observation.record_versions`, `get_as_of`, `get_series`, `has_maturity`, `latest_valid_date` and `current_knowledge_time` through python-oracledb (thin mode, async pool) |
| `persistence.facade` | FastAPI app, contract ↔ domain mapping, problem responses |
| `persistence.api` | Composition root of the `api` process |

import-linter enforces that dependencies point inward and that domain and application import no frameworks, database drivers or contracts.

## Configuration

Environment variables, validated at startup (pydantic-settings):

| Variable | Default | Meaning |
|---|---|---|
| `PERSISTENCE_DB_DSN` | – (required) | Oracle DSN, e.g. `localhost:1521/FREEPDB1` |
| `PERSISTENCE_DB_USER` | `core_app` | Runtime database user |
| `PERSISTENCE_DB_PASSWORD` | – (required) | Its password |
| `PERSISTENCE_DB_POOL_MIN` / `PERSISTENCE_DB_POOL_MAX` | `1` / `4` | Connection pool size |
| `PERSISTENCE_DB_ACQUIRE_TIMEOUT_MS` | `5000` | Maximum wait for a pooled connection |
| `PERSISTENCE_DB_CALL_TIMEOUT_MS` | `30000` | Maximum duration of one database round trip |

Migrations additionally read `PERSISTENCE_DB_ADMIN_PASSWORD` (`SYSTEM`) and `PERSISTENCE_DB_OWNER_PASSWORD` (`CORE`). `PERSISTENCE_DB_PASSWORD` sets the `CORE_APP` password.

## Running locally

```sh
devbox run -- task persistence:setup        # virtual environment
devbox run -- task persistence:db:start     # Oracle Free on localhost:1521, waits until healthy
devbox run -- task persistence:db:migrate   # admin changelog as SYSTEM, then CORE as its owner
devbox run -- task persistence:run          # api process on http://localhost:8001
```

The Taskfile sets local-only default passwords for this database; override them through the environment. `task persistence:db:stop` stops the database, and `task persistence:db:reset` removes it with its data.

## Tests

| Task | Runs |
|---|---|
| `task persistence:test:unit` | Domain, use case, REST facade and configuration; no I/O |
| `task persistence:test:integration` | Oracle Free via Testcontainers (Docker required): migrations, Oracle adapter (versioning, reloads, duplicates, concurrent writers), REST end to end and the utPLSQL suites |

CI: `.github/workflows/persistence.yml` (also triggered by `src/contracts/**`).

## Not yet in place

Transparency interface (`/v1/runs`, lineage, alerts), domain metrics, JSON logs, traces, the `Idempotency-Key` header of [[02-interfaces-and-contracts#REST standards]], the `job` process type and the OpenAPI document in `contracts`. They follow in their own issues.

## Container image

`src/services/persistence/Dockerfile` builds the api image (build context `src/`, because the service uses `contracts`). It runs as a non-root user on port 8001 and is started with the local stack by `task dev:up` (see [[09-deployment]]).
