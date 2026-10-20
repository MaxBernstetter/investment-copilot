# Run History

Ingestion records every `daily`, `history` and `replay` job as one or more attempts in `ING.run`. Each attempt is a row from `start_run` until `finish_run` (or `fail_unfinished_run` for a killed job). The transparency api ([[10-observability]]) reads this history; persistence and orchestration never touch `ING`.

Tracked in [#32](https://github.com/MaxBernstetter/yield-lens/issues/32). Code: `src/services/ingestion/db/`.

## Run, attempt and status

- A **run** is identified by `run_id` (for example `daily_load_ecb-2026-10-16`). Each retry or rerun adds an **attempt** (`1`, then `2`, …) assigned by the database.
- While an attempt is open its status is `running`. `finish_run` sets `succeeded` (no error), `partial` (an error after at least one committed step) or `failed` (an error before any step). A second finish is a no-op: the first outcome wins.
- `fail_unfinished_run` marks every still-`running` attempt of a run id as `failed`; counts stay at zero until finish.

## Table and package

- Table `run`: one row per attempt (`attempt_id` is the paging cursor; unique `(run_id, attempt)`).
- Package `ing_run`: `start_run`, `finish_run`, `fail_unfinished_run`, `get_runs`, `get_run`. The runtime user `ING_APP` may only execute the package, not read the table directly.

## Recording

Each `daily`, `history` and `replay` job opens an attempt with `start_run` before its steps and closes it with `finish_run` when the use case finishes or fails. The run summary JSON includes `attempt`. Usage and configuration errors (exit `2`) and `ingestion-scenario` are not recorded. `ingestion-load-ecb fail-unfinished --run-id ID --error-type TYPE [--error-message TEXT]` marks the attempts of a run id that are still `running` as `failed`; the Airflow load task calls it on retry and on final failure, because a killed task never lets its job finish the attempt. Attempts already finished are left alone. An error after at least one committed window or replayed delivery is `partial`; before any step it is `failed`. A `daily` run has one window, so it is never `partial`.

## Not yet in place

- Ingestion api `GET /v1/runs` and `GET /v1/runs/{run_id}` (PR-5/6).
- Business alerts ([#43](https://github.com/MaxBernstetter/yield-lens/issues/43)).
