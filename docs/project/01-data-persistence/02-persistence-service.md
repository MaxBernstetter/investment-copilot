# Persistence Service

The `persistence` service (`src/services/persistence/`) owns the `CORE` schema and exposes the bitemporal store through REST. The REST facade and the use case are in place; the Oracle adapter and the composition root of the `api` process follow. Data model: [[01-bitemporal-model]]. Design rules: [[11-service-design]].

## Interface (`api` process)

The contract is `contracts.persistence.v1` (`src/contracts/src/contracts/persistence/v1/`).

| Method and path | Purpose | Responses |
|---|---|---|
| `POST /v1/observations/versions` | Record a batch of observations as new versions, all or nothing | `200` `RecordVersionsResponse`; `409` an observation already has an open version; `422` contract violation or an observation appears twice in the batch |
| `GET /health` | Liveness | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: the database answers a ping | `200 {"status": "ready"}`, `503 {"status": "unavailable"}` |

- Request `RecordVersionsRequest`: `observations`, a list of 1 to 10 000 `ObservationVersion` (`curve_id`, `maturity`, `valid_date`, `value`, `origin`, `method_version`, `source_id`, `run_id`, `change_reason`). Larger loads are split into chunks by the caller.
- Response `RecordVersionsResponse`: `recorded_count` and `known_from`, the knowledge time (UTC) that all versions of the batch share.
- Errors are RFC 9457 problem details (`application/problem+json`).
- Knowledge time can't be set through the API; only the database clock sets it.

## Layers

| Package | Content |
|---|---|
| `persistence.domain` | `Observation`, `ObservationKey`, `RecordedVersions`, the rule that a batch names each observation once; domain errors |
| `persistence.application` | `RecordVersions` use case and the `ObservationRepository` port |
| `persistence.facade` | FastAPI app, contract ↔ domain mapping, problem responses |

import-linter enforces that dependencies point inward and that domain and application import no frameworks, database drivers or contracts.

## Tests

| Task | Runs |
|---|---|
| `task persistence:test:unit` | Domain, use case and REST facade; no I/O |
| `task persistence:test:integration` | Oracle Free via Testcontainers (Docker required): migrations and the utPLSQL suites |

CI: `.github/workflows/persistence.yml` (also triggered by `src/contracts/**`).

## Not yet in place

Transparency interface (`/v1/runs`, lineage, alerts), domain metrics, JSON logs, traces, the `Idempotency-Key` header of [[02-interfaces-and-contracts#REST standards]], the `job` process type, the Dockerfile and the OpenAPI document in `contracts`. They follow in their own issues.
