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

## Not yet in place

- Job wiring that calls `start_run` / `finish_run` ([#32](https://github.com/MaxBernstetter/yield-lens/issues/32) PR-3).
- Airflow callback that runs `fail-unfinished` on killed attempts (PR-4).
- Ingestion api `GET /v1/runs` and `GET /v1/runs/{run_id}` (PR-5/6).
- Business alerts ([#43](https://github.com/MaxBernstetter/yield-lens/issues/43)).
