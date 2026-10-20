# Orchestration

Apache Airflow (3.x) schedules and sequences the pipeline. It is a platform component, not a domain: **DAGs contain no business logic**. Each task calls one service operation through its REST interface (see [[0003-rest-and-airflow]]).

## Main DAGs

| DAG | Trigger | Steps |
|---|---|---|
| `daily_load` | Schedule per source (after publication time) | ingest (incl. revision lookback) → schema/completeness gate → record versions → quality gate → derived measures/curves → write–audit–publish marts |
| `backfill` | Manual, with date range | Same steps, mapped over date chunks |
| `replay` | Manual, with date range and normalization version | Rebuild core from raw payloads → gates → marts (see [[12-data-pipeline]]) |
| `recalculation` | Manual, with method version and date range | Recalculate derived values per chunk → refresh marts → impact report (processing) |
| `scenario` | Manual (demo/tests) | Inject simulated events → downstream steps |
| `backup` | Daily | Data Pump export per schema → upload to object storage → verify (see [[0012-backup-and-restore]]) |

`daily_load` is one DAG per source, named `daily_load_<source>`, because each source has its own schedule.

**In place today:** `daily_load_ecb` runs ingest then a quality check on the loaded curve, Monday to Friday at 13:15 Europe/Berlin, for the previous TARGET business day (see [[04-daily-schedule]]). Until the service images exist, each task runs the job's command line as a subprocess instead of a `job` container. DAGs and pools live in `src/orchestration/` (`dags/`, `pools.json`).

## Airflow standards

- **Thin DAGs:**
  - Tasks are HTTP calls to services (TaskFlow API with the HTTP provider).
  - No pandas, SQL or domain logic inside DAG files.
- **Idempotency:** every task is keyed by the data interval (`data_interval_start/end`) and sends an `Idempotency-Key`, so reruns and retries are safe.
- **Time semantics:** schedules use logical dates and data intervals, never `now()`. Backfill = catchup over the same DAG code.
- **Parallelism:**
  - Dynamic task mapping over countries and date chunks.
  - **Pools** cap concurrent load on Oracle.
- **Concurrency:** `max_active_runs = 1` per DAG and interval. Pools of size 1 act as a mutex per curve and range for backfill, replay and recalculation.
- **Gates stop the flow:** a `block` validation result fails the downstream publish task for the affected slice; there is no silent continuation.
- **Lineage:** the OpenLineage provider emits run and dataset events for every task (see [[0013-openlineage]]).
- **Data-aware scheduling:** downstream DAGs are triggered by **Assets** (e.g. `core.observations`) instead of fixed times where possible.
- **Heavy batch work runs as job containers** (see [[0010-api-and-job-process-types]]):
  - Airflow starts the service image in `job` mode per chunk: `DockerOperator` in the demo, `KubernetesPodOperator` at scale.
  - Job containers exit when done, so idle batch capacity is zero.
- **Light commands** go through REST. Long ones return `202` and a run id, which Airflow waits on with deferrable sensors rather than blocking workers.
- **Failure handling:**
  - Retries with exponential backoff.
  - Each service records the failed run in its own run history.
  - Airflow emits OpenTelemetry metrics, so task failures raise a platform alert (see [[10-observability]]).
  - There are no silent failures.
- **Tracing:** each task starts a trace and passes `traceparent` to the service, so a DAG run can be followed across services.
- **Configuration:**
  - Connections and variables come from environment variables and secrets, never from DAG code or the metadata DB UI.
  - DAG files never hold secrets.
- **Testing:** a DAG integrity test (all DAGs import, no cycles, required tags/owners) and task-call contract tests run in CI.
- **Executor:**
  - LocalExecutor for the demo.
  - CeleryExecutor or KubernetesExecutor at scale, with no DAG changes (see [[08-scalability]]).
