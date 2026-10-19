# Scenarios

A scenario is a named sequence of events that writes a simulated curve in steps, so the core can be shown handling gaps, bad values, late values and corrections without touching a real curve. The first scenario, `corrected-yield`, covers the whole cycle. Code: `src/services/ingestion/src/ingestion/` (`domain/scenario.py`, `domain/scenarios.py`, `application/run_scenario.py`, `facade/jobs/scenario.py`).

Tracked in issue #25.

## Isolation

- **Simulated curve:** every event writes to `ecb-aaa-spot-sim`. Scenarios never write to `ecb-aaa-spot`, the real curve.
- **Source id:** every value carries `source_id = scenario`, so simulated values are told apart from published ones. The store rejects a write that mixes simulated and real data.
- **No source call:** a scenario reads no source and no raw delivery in `ING`. It writes through the persistence write interface only.
- **Insert only:** nothing is removed or rewritten. Isolation replaces removal: a scenario lives on its own curve, so the real curves stay as they were.

## Events of `corrected-yield`

Each event writes its values with the change reason `initial`, except the correction, which writes `correction`.

| Event | Kind | Writes |
|---|---|---|
| `publish` | publish | The simulated curve for 2026-10-05 and 2026-10-06, all 11 tenors. |
| `gap` | gap | 2026-10-07 without the 10Y and 30Y yields. |
| `bad-value` | bad value | The 10Y yield of 2026-10-08 with an implausible 26.40. |
| `late-value` | late value | The missing 10Y (2.63) and 30Y (3.03) yields of 2026-10-07, arriving late. |
| `correction` | correction | The 10Y yield of 2026-10-08 corrected to 2.64. |

## Time

- **Real time:** events run one after another, with a 2 s pause between two events, so a picker that works in seconds can land between two events.
- **No backdated knowledge time:** the knowledge time of each version is the database clock of persistence at write time ([[0017-commit-safe-knowledge-time]]). A scenario never sets a past knowledge time, so the as-of answers it shows are the answers the system gives in operation.

## Commands

```sh
ingestion-scenario corrected-yield [--event NAME]...
```

- `--event NAME` (repeatable) runs only the named events, in the order given. Without it, all events run in order.
- **Output:** one JSON line on stdout (`scenario_finished`: the curve, and per event its name, kind, run id, recorded and unchanged counts, and `known_from`).
- **Failure:** one JSON line on stderr (`scenario_failed`, error type and message).
- **Exit status:** `0` the scenario finished; `1` a write was rejected or the persistence api failed; `2` usage or configuration error (unknown scenario or event, missing settings).
- **Configuration:** the job reads the shared ingestion settings, so `INGESTION_DB__DSN` and `INGESTION_DB__PASSWORD` must be set even though the scenario does not use `ING` (the Taskfile sets local defaults).

## Tasks

- `devbox run -- task dev:scenario:corrected-yield`: runs the scenario in the local development stack (the `ingestion` container, after `task dev:up`).
- `task ingestion:scenario NAME=corrected-yield`: runs it on the host, against a running persistence api (`task persistence:run`).

## Reruns

A rerun adds versions to the simulated curve, so its history grows with every run. For a clean demo, run `devbox run -- task dev:reset`, then `devbox run -- task dev:up`, and run the scenario again.
