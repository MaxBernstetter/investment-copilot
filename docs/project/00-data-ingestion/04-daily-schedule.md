# Daily ECB Schedule

The Airflow DAG `daily_load_ecb` runs the [[03-ecb-load|ECB curve load]] every TARGET business day after the ECB has published, and retries transient failures within the [[12-data-pipeline#Source access policy|source access policy]].

Tracked in [#21](https://github.com/MaxBernstetter/yield-lens/issues/21). Code: `src/orchestration/dags/daily_load_ecb.py`, with its steps in `src/orchestration/src/orchestration/ecb_daily_load.py` and the calendar in `orchestration/target_calendar.py`.

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

## How the task runs the job

The ingestion service has no image and no `job` container yet, so the task runs the job's command line `ingestion-load-ecb daily --valid-date … --run-id …` as a subprocess on the Airflow worker. The command must be on the worker's `PATH` and the worker needs the job's environment (`INGESTION_PERSISTENCE__URL`, `INGESTION_SOURCES__ECB__*`). Once the ingestion image exists, the task starts it as a `job` container instead ([[0010-api-and-job-process-types]]); the exit-status contract stays the same.

## Pools

Pools are created from `src/orchestration/pools.json` with `task orchestration:pools:import` (needs a migrated metadata DB in `AIRFLOW_HOME`). A task in a pool that does not exist is never scheduled, so the DAG tests check that every pool a DAG uses is in `pools.json`.

## Tests

`task orchestration:test:unit` runs without a running Airflow or a metadata DB:

| Test | Proves |
|---|---|
| `tests/unit/test_dags.py` | Every DAG imports, uses only pools from `pools.json`, has tags and an owner; the timetable fires Monday to Friday at 13:15 Berlin across the change to winter time; `max_active_runs = 1`, no catchup; 2 retries, the failure callback and the `ecb` pool of size 1 |
| `tests/unit/test_ecb_daily_load.py` | Valid date per run day, skip on TARGET holidays, the job command, exit status mapping (retry on `1`, no retry on `2`), job output in the log, the JSON failure line |
| `tests/unit/test_target_calendar.py` | TARGET closing days, moving Easter, previous business day across weekends, holidays and the year end |

## Not yet in place

- Recording runs in the ingestion run history and the transparency interface ([#32](https://github.com/MaxBernstetter/yield-lens/issues/32)), alerting on final failures ([#43](https://github.com/MaxBernstetter/yield-lens/issues/43)).
- Deployment of Airflow itself (Compose stack with its Postgres metadata DB, `AIRFLOW_HOME`, importing the pools on start).
- OpenLineage events and `traceparent` propagation from the task.
