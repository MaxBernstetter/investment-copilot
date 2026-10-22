# Processing service

The `processing` service owns the quality rules of YieldLens: it checks the published curves and keeps the results. This note describes the skeleton: its layers, its process types, its configuration and its tasks. The checks follow with [#30](https://github.com/MaxBernstetter/yield-lens/issues/30) (completeness) and [#31](https://github.com/MaxBernstetter/yield-lens/issues/31) (plausibility, see [[01-plausibility-thresholds]]).

## Layers

The service follows the hexagonal layout of the other services (see [[11-service-design]]). The import-linter contract in `pyproject.toml` enforces the direction:

- `processing.api`: composition root of the `api` process; wires the adapters into the facade.
- `processing.facade`: REST facade (`rest/app.py`): `contracts.processing.v1` quality routes, `/health`, `/ready` and RFC 9457 problems.
- `processing.infrastructure`: Oracle adapter (`proc.py`), the only place that imports `oracledb`.
- `processing.application` and `processing.domain`: use cases and rules. No I/O, no frameworks, no contracts.

## Process types

One image, two process types (see [[09-deployment]]):

| Process | Status | Command |
|---|---|---|
| `api` | quality reads, derived measures plus health and readiness | `uvicorn --factory processing.api:create_app_from_environment --port 8002` |
| `job` | quality check over a date range | `processing-check-quality CURVE_ID --from D --to D [--run-id ID]` |

## Interface (`api` process)

| Route | Parameters | Answers | Errors |
|---|---|---|---|
| `GET /v1/curves/{curve_id}/quality` | `from`, `to`, `as_of` | Quality per TARGET business day | 404 unknown curve; 422 invalid range or `as_of` |
| `GET /v1/curves/{curve_id}/value-quality` | `from`, `to`, `maturity`, `as_of` | Quality per published value | 404 unknown curve; 422 invalid range or `as_of` |
| `GET /v1/curves/{curve_id}/measures` | `from`, `to`, `as_of` | Spreads, curvature and inversion per valid date, see [[04-derived-measures]] | 404 unknown curve; 422 `from` after `to`, a range over 3660 days, or a future `as_of` |

The measures are computed on read from the persistence service (grid and series) and the PROC quality results, so the route needs `PROCESSING_PERSISTENCE__URL`. An unreachable persistence service is a 500 problem.

The PROC schema (`check_run`, `checked_day`, `value_quality`, `quality_finding`) is created by the Liquibase changelogs in `db/` (`db/admin` as SYSTEM, then `db/proc` as the owner `proc`). The runtime user `proc_app` has `CREATE SESSION` and nothing else until the check use case adds its grants. Its integration tests start Oracle Free with Testcontainers and check the migrations, the privileges and the readiness probe.

`/health` answers `{"status": "ok"}` while the process is up. `/ready` answers `{"status": "ready"}` when a connection to the processing database succeeds, and 503 `{"status": "unavailable"}` otherwise.

Logs are JSON lines on stderr (`log_config.json`). Every line logged inside a span carries `trace_id` and `span_id`; the job's summary and failure lines carry the ids of its root span.

## Errors

Errors are RFC 9457 problems. An unexpected error is a `500` problem (*Internal server error*) with a generic detail and `trace_id` when traced; the exception and traceback are logged at ERROR.

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
| `PROCESSING_PERSISTENCE__URL` | none (required) | Base URL of the persistence service, read by the job and by the measures route, e.g. `http://localhost:8001` |
| `PROCESSING_PERSISTENCE__TIMEOUT_SECONDS` | `30` | Timeout per persistence request |

The telemetry follows the standard OpenTelemetry variables. Traces and metrics are exported over OTLP/HTTP only when an endpoint is set; without one the service runs and records nothing outside the process.

| Variable | Default | Meaning |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | none | Collector base URL, e.g. `http://localhost:4318`. None means no export |
| `OTEL_SERVICE_NAME` | `unknown_service` | Service name on every span and metric |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `cumulative` | Temporality of the exported metrics; set `delta` for the job, which exports once at exit |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `http` in the image | Current HTTP semantic conventions |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` | `health,ready` in the image | Probe routes that are not traced |

The Oracle spans (`proc_quality.<operation>`, CLIENT) are written by hand: no maintained instrumentation covers async `oracledb` pools or `callfunc`. Each one puts the trace id into the session's `CLIENT_IDENTIFIER` and `CLIENT_INFO`, so database views can be joined to a trace.

The Taskfile supplies local development defaults for the DSN, the password and the persistence URL. Override them through the environment; never reuse them outside your machine.

The `job` process reads the latest curve grid and maturity series from persistence, assesses the range in chunks and records the result in the PROC schema. Exit codes: `0` finished (also when the curve is unknown to persistence), `1` persistence or Oracle failure, `2` usage or configuration error (including a curve with no thresholds). It logs one JSON summary line to stdout on success and one failure line to stderr otherwise.

## Observability

The metrics are OpenTelemetry instruments. Their names are already the Prometheus names, so the collector exports them unchanged. The `job` process exports them once at exit (set `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`); the `api` process reports the two gauges at each collection.

| Metric | Type | Labels | Process | Meaning |
|---|---|---|---|---|
| `yl_processing_quality_checks_total` | counter | `curve`, `status` | job | Checks per invocation. `status` is the worst day status (`passed`, `info`, `warn`) of a finished check, or `failed` when the run failed |
| `yl_processing_quality_findings_total` | counter | `curve`, `rule`, `severity` | job | Findings per rule and severity |
| `yl_processing_values_checked_total` | counter | `curve` | job | Values assessed |
| `yl_processing_quality_check_duration_seconds` | histogram (s) | `curve` | job | Duration of a check run |
| `yl_processing_alert_active` | gauge | `curve`, `alert` (`quality-warn`) | api | 1 when the alert is active for the curve, else 0 |
| `yl_processing_quality_last_success_timestamp_seconds` | gauge (s) | `curve` | api | Time of the latest check run of the curve |
| `http_server_request_duration_seconds` | histogram (s) | `http_route`, `http_request_method`, `http_response_status_code` | api | Golden signals of the API: rate, errors and duration. Emitted by the FastAPI instrumentation |

Traces cover the `api` requests, the `job` run, the persistence calls and the Oracle spans. Service names are `processing-api` and `processing-job`. The trace id of a job run is in the database session as `CLIENT_IDENTIFIER` and `CLIENT_INFO` (see [Configuration](#configuration)).

### Alert: quality-warn

The alert is active for a curve when the latest `check_run` of the curve has at least one `checked_day` with status `warn`. "Latest" is the row with the most recent `recorded_at`. The rule is `observability/alerts/quality-warn.yaml`, and it fires once per `curve` while the gauge is above 0. Its panel is in the dashboard `observability/dashboards/processing.json`, the Processing dashboard. The platform (#138) provisions both files into Grafana.

The dashboard has three rows. **API** shows the request rate, the 5xx ratio and the p95 duration. **Quality checks** shows checks by status, findings by rule and severity, values checked, the check duration, the alert state and the time since the last check. **Traces** links to recent Tempo traces of both processes. Links go to Tempo only: there are no logs in Grafana.

## Runbook: quality warn

The alert `quality-warn` is active for a curve (see [Alert: quality-warn](#alert-quality-warn)).

1. Open the Processing dashboard and filter by the `curve` of the alert. Check the findings panel for the rule.
2. Read the days and findings on the processing api: `GET /v1/curves/{curve_id}/quality?from=…&to=…`, then `GET /v1/curves/{curve_id}/value-quality?from=…&to=…[&maturity=…]` for the flagged days.
3. Decide: the source value is wrong (wait for or request a source correction, which ingestion loads), or the threshold is wrong (change the rule config through an issue).
4. After the correction is loaded, rerun `processing-check-quality CURVE_ID --from D --to D`. The alert clears with the next run that has no `warn` day.
5. Caveat: "latest" is the last chunk's `check_run`. A job over more than 366 days writes one row per chunk, so a `warn` in an earlier chunk is not reflected by the alert. Rerun over the affected range alone to see it.

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
- `task processing:openapi`: export the processing OpenAPI document to `src/contracts/openapi/processing/v1.json`; the committed document is checked for staleness by a unit test (`tests/unit/test_openapi.py`), so regenerate it after any route change
