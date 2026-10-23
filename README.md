# yield-lens

**YieldLens** — an explorable, auditable and historically reproducible government bond yield dataset.

&nbsp;

## Quick look

With Docker and [devbox](https://www.jetify.com/devbox) installed:

```sh
devbox shell
task stack:up      # first run builds images: a few minutes
```

Then open the explorer at <http://localhost:5174> (the URL `stack:up` prints, if you changed the ports). The latest ECB curve is shown first. No hosted demo is live yet; the full walkthrough is under [Try it locally](#try-it-locally).

&nbsp;

## Why

Yield curves feed risk calculations, valuation and investment decisions. Most tools show only the latest value and overwrite history. YieldLens keeps every value it has ever known:

- **Bitemporal history**
  - Every value has a valid time (the date it applies to) and a knowledge time (when the platform learned it).
  - Corrections add versions; nothing is overwritten.
- **Time travel**
  - Every view and API call accepts an as-of time.
  - "What did the platform show last Tuesday, based on what it knew then?"
- **Provenance**
  - Every value links to its source delivery and ingestion run.

&nbsp;

## What it does today

- Loads the ECB euro area AAA spot curve (3M–30Y).
- Stores it bitemporally in Oracle.
- Checks every value against plausibility and completeness rules.
- Serves it through a read-only API and a browser explorer.
- Runs daily loads in Airflow (optional locally).

The explorer offers:

- Curve, overlay, time-series, changes and quality views
- Quality badges with explanations on every flagged value
- Version history per value
- Time travel

More in [docs/idea/](docs/idea/) and [ARCHITECTURE.md](ARCHITECTURE.md).

&nbsp;

## Try it locally

**Prerequisites**

- Docker with Compose
- [devbox](https://www.jetify.com/devbox) — provides `task`, Node and the other tools in pinned versions

**Quickstart**

1. **Configure ports** (optional, see [Ports](#ports)): `cp .env.example .env`
2. **Open the toolchain shell:** `devbox shell`
3. **Start everything:** `task stack:up`
   - Starts Oracle, runs the migrations, starts the four APIs and waits until they are healthy.
   - Loads ECB and US Treasury history since 2024-01-01 unless all three real curves already have data (live calls). Less history: `SEED_START=2026-01-01 task stack:up`
   - Starts the explorer in the background (log: `.task/stack/frontend.log`).
   - Prints the explorer and API URLs. First run builds images: a few minutes.
   - Safe to run again.
4. **Stop:** `task stack:down` — keeps the data. `task dev:reset` removes it.

**Explore**

- Open the explorer: the latest curve is shown first.
- Pick another valid date, overlay dates, switch to one maturity's time series.
- See what changed in the Changes view; check the data in the Quality view.
- **Travel in time:** open the `?as_of=` link printed by the seed (`task dev:seed`).
  - The explorer shows only what the platform knew then (latest curve about 20 business days older).
  - "Now" returns to today.
- **See a correction:** `task dev:scenario:corrected-yield`
  - Plays publish, gap, bad value, late value, correction on the simulated curve `ecb-aaa-spot-sim`.
  - Pick that curve in the explorer to see quality flags, changes and each value's version history.

**Step by step** (what `stack:up` does): `task dev:up`, `task dev:seed`, `task frontend:dev`.

**API**

- <http://localhost:8000> (or your `ACCESS_PORT`)
- Example: `curl localhost:8000/v1/curves/ecb-aaa-spot/observations`
  - Replace `8000` with your `ACCESS_PORT` if you changed it.

&nbsp;

## Ports

Dev machines often run many containers, so no port is assumed free. Every host port is set in `.env`.

- `cp .env.example .env`, then change the values.
- Unset values fall back to the defaults below.
- Only the host side changes; containers still talk to each other on their internal ports.
- Use `task` commands (`stack:*`, `dev:*`): they load `.env`. Bare `docker compose` does not.
- Setting `FRONTEND_PORT` also updates the API's allowed origin. Re-run `task stack:up`.

| Variable | Service | Default |
|---|---|---|
| `PERSISTENCE_DB_PORT` | Oracle | 1521 |
| `ACCESS_PORT` | access API | 8000 |
| `PERSISTENCE_PORT` | persistence API | 8001 |
| `PROCESSING_PORT` | processing API | 8002 |
| `INGESTION_PORT` | ingestion API | 8003 |
| `FRONTEND_PORT` | explorer | 5174 |
| `AIRFLOW_PORT` | Airflow UI (optional) | 8088 |
| `PROMETHEUS_PORT` | Prometheus (optional) | 9090 |
| `TEMPO_PORT` | Tempo (optional) | 3200 |
| `GRAFANA_PORT` | Grafana (optional) | 3300 |

**Browsers refuse some ports.** Chrome and Firefox block 6665–6669 (`ERR_UNSAFE_PORT`) and a few others, such as 6000 and 6697.

- Give anything you open in a browser a safe port: `FRONTEND_PORT`, `ACCESS_PORT`, `AIRFLOW_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT`.
- The other services are only reached by tools and can use blocked ports.
- Example for a 6661–6670 range: browser-facing on 6661–6664 and 6670, the rest on 6665–6669.

&nbsp;

## Optional: Airflow

- Start: `task dev:airflow:up`
- UI: <http://127.0.0.1:8088> (your `AIRFLOW_PORT`)
- Login: `airflow` / `airflow`
  - Created by the `airflow-init` service (`_AIRFLOW_WWW_USER_*` in `src/deploy/compose.yaml`), not an Airflow default.
- Stop: `task dev:airflow:down`

&nbsp;

## Optional: observability

- Start: `task dev:obs:up`
- Starts:
  - OpenTelemetry Collector
  - Prometheus — <http://127.0.0.1:9090>
  - Tempo — port 3200
  - Grafana — <http://127.0.0.1:3300> (user `admin`, password `LocalGrafana_1` unless `GRAFANA_ADMIN_PASSWORD` is set)
- Includes the processing dashboard and the `quality-warn` alert.
- Ports above are defaults; see [Ports](#ports).

Related tasks:

- `task dev:obs:smoke` — checks the wiring
- `task dev:obs:firing-check` — shows the alert firing and clearing
- `task dev:obs:down` — stops it

&nbsp;

## Develop

1. Clone, run `devbox shell`, then `task toolchain:setup` once to install the git hooks.
2. Set up the components you work on: `task <component>:setup`
   - Components: `access`, `contracts`, `frontend`, `ingestion`, `orchestration`, `persistence`, `processing`
   - `task --list` shows every task.
3. Run the same checks as CI:
   - `task <component>:lint`, `:typecheck`, `:test:unit`
   - `task toolchain:lint` runs all pre-commit hooks.
   - Integration tests (`persistence`, `ingestion`, `processing`) need Docker.
4. For agent-driven work with the GitHub board, export a `GITHUB_PAT` as in [GitHub MCP connection](docs/development/02-github-mcp.md).

**Read before changing code**

- [AGENTS.md](AGENTS.md) — working rules for humans and agents (board, PR size, worktrees, subagents)
- [Development principles](docs/development/principles/README.md) and the Definition of done
- [Task management](docs/development/01-task-management.md) — issues, board and pull requests
- [Build, tasks and CI](docs/architecture/13-build-and-ci.md) — Taskfiles, workflows, required checks
- [Agent harness](docs/development/03-agent-harness.md) — which model does what in agentic development

The `docs/` folder is an Obsidian vault; start at [docs/README.md](docs/README.md).
