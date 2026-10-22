# Daily ECB Schedule

The Airflow DAG `daily_load_ecb` runs the [[03-ecb-load|ECB curve load]] every TARGET business day after the ECB has published, and retries transient failures within the [[12-data-pipeline#Source access policy|source access policy]].

Tracked in [#21](https://github.com/MaxBernstetter/yield-lens/issues/21). Code: `src/orchestration/dags/daily_load_ecb.py`, with load steps in `src/orchestration/src/orchestration/ecb_daily_load.py`, quality-check commands in `orchestration/quality_check.py`, and the calendar in `orchestration/target_calendar.py`.

## When it runs and what it loads

| Rule | Value |
|---|---|
| Schedule | `CronTriggerTimetable("15 13 * * 1-5", timezone="Europe/Berlin")`: Monday to Friday at 13:15, summer and winter time alike |
| Why 13:15 | The ECB publishes at about 12:00 CET/CEST on TARGET business days ([[01-data-sources#Publication timing]]); the offset keeps the load off the publication minute |
| Valid date | The previous TARGET business day before the run day (Monday loads Friday, the Tuesday after Easter loads Maundy Thursday). The job's lookback window re-fetches the days before it |
| TARGET holiday | The task is skipped (`AirflowSkipException`), so the run ends as success with a skipped task, not as a failure |
| Run id | `daily_load_ecb-<valid date>`, so a retry or rerun reuses it |
| Catchup | Off. A missed day is covered by the next run's lookback window; longer gaps are the backfill ([#27](https://github.com/MaxBernstetter/yield-lens/issues/27)) |
| Concurrency | `max_active_runs = 1` and the task runs in the pool `ecb` of size 1, so there is never more than one ECB load at a time |

TARGET is closed on weekends, 1 January, Good Friday, Easter Monday, 1 May, 25 and 26 December. The calendar decides when to run; completeness checks against market calendars are processing's job ([[12-data-pipeline#Reference data]]).

## Retries and failures

| Job exit status | Meaning (see [[03-ecb-load#Commands]]) | Airflow |
|---|---|---|
| `0` | Load finished, also with zero rows | Success |
| `1` (or any other non-zero status) | Load failed (request failed, payload invalid, write rejected, kill switch) | Retried: at most 2 retries, after 10–20 and 20–40 minutes (exponential backoff from 10 minutes, with jitter) |
| `2` | Usage or configuration error | Fails at once (`AirflowFailException`); a retry cannot help |

- With at most 3 attempts per request inside the source client ([[02-source-client]]) and 3 task attempts, one failing load costs at most 9 requests.
- A task attempt is cut off after 30 minutes (`execution_timeout`) and then retried like any failure.
- The job's JSON output (`load_finished`, `load_failed`) goes into the task log.
- When the task has failed for good, the failure callback logs one JSON line at `ERROR`: `event = task_failed`, `dag_id`, `task_id`, `run_id`, `try_number`, `error`, `message`. The failed task and run also stay in Airflow's run history.
- A retried or finally failed load task runs `ingestion-load-ecb fail-unfinished` in Docker, which marks the still-running attempt of its run `failed` (the error type is the exception class: `AirflowTaskTimeout` when Airflow killed the task; `AttemptNotFinished` when the task has no exception). The run id comes from XCom (`ingestion_run_id`), which the load task pushes before it starts the job.

## How the tasks run the jobs

The ingestion and processing job images are built and tagged locally when you start the opt-in Airflow Compose profile (`task dev:airflow:up`). Each task starts the matching `job` container on the Compose network via `orchestration/job_runner.py` ([[0010-api-and-job-process-types]]); the exit-status contract is unchanged.

| Task | Command (entrypoint + argv in the container) | Run id |
|---|---|---|
| `load_ecb` | `ingestion-load-ecb daily --valid-date … --run-id …` | `daily_load_ecb-<valid date>` |
| `check_quality` | `processing-check-quality <curve> --from <valid date − 21d> --to <valid date> --run-id …`, mapped once per curve in `CURVE_IDS` (`ecb-aaa-spot`, `ecb-all-spot`) | `daily_load_ecb-check-<curve>-<valid date>` |

`check_quality` runs after `load_ecb` in the default pool (not `ecb`), with the same retry and failure rules. A failing check of one curve does not stop the other. The Airflow worker passes through `INGESTION_*` and `PROCESSING_*` from the stack environment. Image tags come from `YIELDLENS_INGESTION_JOB_IMAGE` and `YIELDLENS_PROCESSING_JOB_IMAGE` (set in the `airflow` Compose profile).

## Backfill

The DAG `backfill_ecb` loads a date range by hand. Code: `src/orchestration/dags/backfill_ecb.py`, with the year split and the command in `src/orchestration/src/orchestration/ecb_backfill.py`.

Trigger it from the Airflow UI with the parameters `start` and `end` (inclusive dates), or from the CLI:

```sh
airflow dags trigger backfill_ecb --conf '{"start":"2004-09-06","end":"2024-12-31"}'
```

- The range is split into one chunk per calendar year. The first and last chunk are clipped to `start` and `end`. Each chunk is one `ingestion-load-ecb history --start … --end … --run-id backfill_ecb-<start>-<end>` run, then `processing-check-quality <curve> --from <start> --to <end> --run-id backfill_ecb-check-<curve>-<start>-<end>` for each curve in `CURVE_IDS`.
- Loads run one after another in the `ecb` pool; quality checks for each chunk run after its load in the default pool. A backfill never runs next to the daily load. The retry and failure rules of the daily load apply to each task.
- Rerunning a range is safe: a value that is already stored and unchanged is a no-op, thanks to versioning ([[03-ecb-load#Not yet in place]], [#15](https://github.com/MaxBernstetter/yield-lens/issues/15)).
- `start` after `end` is rejected by the planning task before any chunk runs.

### Loading the all-issuer history (#264)

The all-issuer curve `ecb-all-spot` starts with the same history as the AAA curve, but its values are not stored yet. Load them with the backfill runbook:

- **On a stack with the Airflow profile:** trigger `backfill_ecb` with `{"start":"2004-09-06","end":"<yesterday>"}` (about 23 requests). The AAA values come again in the same requests and are no-ops.
- **Without Airflow:** `task dev:seed START=2004-09-06` on a stack that may be written (see [[01-data-sources]]).
- **Expected `warn` days for `ecb-all-spot`:** 2008-10-08, 2009-01-23 and 2010-10-15 (the quality-warn alert may fire for these year chunks). The method is in [[01-plausibility-thresholds#All-issuer curve]].
- **Record the result:** as a comment on [#264](https://github.com/MaxBernstetter/yield-lens/issues/264), the `load_finished` line of each year (`attempt`, `delivered_count`, `recorded_count`, `unchanged_count`) and the check status per curve.

## Pools

Pools are defined in `src/orchestration/pools.json`. With the local Airflow profile, `airflow-init` imports them into the metadata DB on first start. You can re-import manually with `task orchestration:pools:import` when `AIRFLOW_HOME` points at that environment. A task in a pool that does not exist is never scheduled, so the DAG tests check that every pool a DAG uses is in `pools.json`.

## Tests

`task orchestration:test:unit` runs without a running Airflow or a metadata DB:

| Test | Proves |
|---|---|
| `tests/unit/test_dags.py` | Every DAG imports, uses only pools from `pools.json`, has tags and an owner; the timetable fires Monday to Friday at 13:15 Berlin across the change to winter time; `max_active_runs = 1`, no catchup; 2 retries, the failure callback and the `ecb` pool of size 1; `check_quality` after `load_ecb`, once per curve; one ECB task per daily run; the backfill is manual with load then quality check per year chunk and curve |
| `tests/unit/test_ecb_backfill.py` | The year split (clipped first and last chunk, one chunk within a year, `start` after `end` rejected) and the `history` command |
| `tests/unit/test_ecb_daily_load.py` | Valid date per run day, skip on TARGET holidays, the job command, exit status mapping (retry on `1`, no retry on `2`), job output in the log, the JSON failure line |
| `tests/unit/test_job_runner.py` | Image env mapping, argv split, forwarded env keys, missing image → fail-fast |
| `tests/unit/test_quality_check.py` | The daily three-week window and the range check argv |
| `tests/unit/test_target_calendar.py` | TARGET closing days, moving Easter, previous business day across weekends, holidays and the year end |

## Not yet in place

- Alerting on final failures ([#43](https://github.com/MaxBernstetter/yield-lens/issues/43)).
- OpenLineage events and `traceparent` propagation from the task.
