# Run History

Ingestion records every `daily`, `history` and `replay` job as one or more attempts in `ING.run`. Each attempt is a row from `start_run` until `finish_run` (or `fail_unfinished_run` for a killed job). The transparency api ([[10-observability]]) reads this history; persistence and orchestration never touch `ING`.

Tracked in [#32](https://github.com/MaxBernstetter/yield-lens/issues/32). Code: `src/services/ingestion/db/`.

## Run, attempt and status

- A **run** is identified by `run_id` (for example `daily_load_ecb-2026-10-16`). Each retry or rerun adds an **attempt** (`1`, then `2`, …) assigned by the database.
- While an attempt is open its status is `running`. `finish_run` sets `succeeded` (no error), `partial` (an error after at least one committed step) or `failed` (an error before any step). A second finish is a no-op: the first outcome wins.
- `fail_unfinished_run` marks every still-`running` attempt of a run id as `failed`; counts stay at zero until finish.

## Table and package

- Table `run`: one row per attempt (`attempt_id` is the paging cursor; unique `(run_id, attempt)`).
- Package `ing_run`: `start_run`, `finish_run`, `fail_unfinished_run`, `get_runs`, `get_run`, `get_alert_attempts`. The runtime user `ING_APP` may only execute the package, not read the table directly.

## Recording

Each `daily`, `history` and `replay` job opens an attempt with `start_run` before its steps and closes it with `finish_run` when the use case finishes or fails. The run summary JSON includes `attempt`. Usage and configuration errors (exit `2`) and `ingestion-scenario` are not recorded. `ingestion-load-ecb fail-unfinished --run-id ID --error-type TYPE [--error-message TEXT]` marks the attempts of a run id that are still `running` as `failed`; the Airflow load task calls it on retry and on final failure, because a killed task never lets its job finish the attempt. Attempts already finished are left alone. An error after at least one committed window or replayed delivery is `partial`; before any step it is `failed`. A `daily` run has one window, so it is never `partial`.

## Ingestion api

Two `GET` endpoints of the transparency interface serve this history as `contracts.transparency.v1` runs with `service = "ingestion"`:

- `GET /v1/runs`: attempts newest first. `from` and `to` are inclusive UTC dates on `started_at` (`from` is 00:00 UTC of its day, `to` runs to the end of its day). `limit` is 1 to 200, default 50. `cursor` is the last `attempt_id` of the previous page (`meta.next_cursor`, null on the last page); the next page continues before it. A running attempt has `finished_at` and `duration_seconds` null.
- `GET /v1/runs/{run_id}`: every attempt of one run id in attempt order.

Errors are RFC 9457 problem details (`application/problem+json`): `422` for an invalid query, including `from` after `to`, and `404` when no attempt of the run id exists. An unexpected error is a `500` problem (*Internal server error*) with a generic detail and `trace_id` when traced; the exception and traceback are logged at ERROR.

## Alerts

Two run alerts are raised from this history ([#43](https://github.com/MaxBernstetter/yield-lens/issues/43)). They are evaluated in `ingestion.application.alerts` from the attempts that `get_alert_attempts` returns.

- An **episode** belongs to one operation (`daily`, `history` or `replay`) and one rule. Attempts are ordered by `attempt_id`. A `run_failed` episode is the run of `failed` attempts after the operation's last `succeeded` attempt. The next `succeeded` attempt clears it. A `run_partial` episode works the same way for `partial` attempts. A `partial` attempt does not open or clear `run_failed`, and a `failed` attempt does not open or clear `run_partial`. `running` attempts are ignored.
- Severity: `run_failed` is `critical`, `run_partial` is `warning`.
- `since` is the `finished_at` of the episode's first failing attempt. `cleared_at` is the `finished_at` of the succeeded attempt that cleared it, and null while the alert is active.
- `run_id`, `attempt` and `cause` point to the episode's latest failing attempt. `cause` is `error_type: error_message`, or only `error_type` when there is no message, cut to 4000 characters.
- `alert_id` is `{name}-{attempt_id}` of the episode's first failing attempt. It stays the same while the alert is active. A failure after a clear opens a new episode with a new id.
- `GET /v1/alerts` returns the active alerts plus alerts cleared within the last 7 days, sorted by `since`, newest first. Older cleared alerts are dropped. The query reads only from the last success before that 7-day window, so the cost stays bounded per operation.
- Acknowledgements arrive in MR 2 of #43. Until then `acknowledged_at` is always null.
- Overlapping attempts of one operation are judged in `attempt_id` (start) order, not in finish order.
