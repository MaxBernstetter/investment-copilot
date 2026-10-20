# Processing service

The `processing` service owns the quality rules of YieldLens: it checks the published curves and keeps the results. This note describes the skeleton: its layers, its process types, its configuration and its tasks. The checks follow with [#30](https://github.com/MaxBernstetter/yield-lens/issues/30) (completeness) and [#31](https://github.com/MaxBernstetter/yield-lens/issues/31) (plausibility, see [[01-plausibility-thresholds]]).

## Layers

The service follows the hexagonal layout of the other services (see [[11-service-design]]). The import-linter contract in `pyproject.toml` enforces the direction:

- `processing.api`: composition root of the `api` process; wires the adapters into the facade.
- `processing.facade`: REST facade (`rest/app.py`): `/health`, `/ready` and RFC 9457 problems.
- `processing.infrastructure`: Oracle adapter (`proc.py`), the only place that imports `oracledb`.
- `processing.application` and `processing.domain`: use cases and rules. No I/O, no frameworks, no contracts.

## Process types

One image, two process types (see [[09-deployment]]):

| Process | Status | Command |
|---|---|---|
| `api` | skeleton: health and readiness | `uvicorn --factory processing.api:create_app_from_environment --port 8002` |
| `job` | quality check over a date range | `processing-check-quality CURVE_ID --from D --to D [--run-id ID]` |

The PROC schema (`check_run`, `checked_day`, `value_quality`, `quality_finding`) is created by the Liquibase changelogs in `db/` (`db/admin` as SYSTEM, then `db/proc` as the owner `proc`). The runtime user `proc_app` has `CREATE SESSION` and nothing else until the check use case adds its grants. Its integration tests start Oracle Free with Testcontainers and check the migrations, the privileges and the readiness probe.

`/health` answers `{"status": "ok"}` while the process is up. `/ready` answers `{"status": "ready"}` when a connection to the processing database succeeds, and 503 `{"status": "unavailable"}` otherwise.

Logs are JSON lines on stderr (`log_config.json`).

## Configuration

Read from environment variables with the prefix `PROCESSING_`, validated at startup. The database settings are nested with `__`:

| Variable | Default | Meaning |
|---|---|---|
| `PROCESSING_DB__DSN` | none (required) | Oracle DSN, e.g. `localhost:1521/FREEPDB1` |
| `PROCESSING_DB__PASSWORD` | none (required) | Password of the `proc_app` user |
| `PROCESSING_DB__USER` | `proc_app` | Database user |
| `PROCESSING_DB__POOL_MIN` / `_POOL_MAX` | `1` / `4` | Connection pool size |
| `PROCESSING_DB__ACQUIRE_TIMEOUT_MS` | `5000` | Wait for a free connection |
| `PROCESSING_DB__CALL_TIMEOUT_MS` | `30000` | Timeout per database call |
| `PROCESSING_PERSISTENCE__URL` | none (required for the job) | Base URL of the persistence service, e.g. `http://localhost:8001` |
| `PROCESSING_PERSISTENCE__TIMEOUT_SECONDS` | `30` | Timeout per persistence request |

The Taskfile supplies local development defaults for the DSN, the password and the persistence URL. Override them through the environment; never reuse them outside your machine.

The `job` process reads the latest curve grid and maturity series from persistence, assesses the range in chunks and records the result in the PROC schema. Exit codes: `0` finished (also when the curve is unknown to persistence), `1` persistence or Oracle failure, `2` usage or configuration error (including a curve with no thresholds). It logs one JSON summary line to stdout on success and one failure line to stderr otherwise.

## Tasks

Run from the repository root (namespace `processing`, see [[13-build-and-ci]]):

- `task processing:setup`: create the virtual environment from `uv.lock`
- `task processing:lint`: ruff, format check and import-linter
- `task processing:typecheck`: mypy (strict)
- `task processing:test:unit`: unit tests, no I/O
- `task processing:test:integration`: integration tests against Oracle Free (Testcontainers; applies the PROC migrations)
- `task processing:db:migrate`: apply the PROC changelogs to the local database started by `persistence:db:start`
- `task processing:run`: run the `api` process on port 8002
- `task processing:check-quality CURVE=… FROM=… TO=…`: run the quality check job locally
