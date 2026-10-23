# yield-lens

**YieldLens** — an explorable, auditable and historically reproducible government bond yield dataset.

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

**Steps**

1. **Configure ports** (optional, see [Ports](#ports)): `cp .env.example .env`
2. **Open the toolchain shell:** `devbox shell`
3. **Start the stack:** `task dev:up`
   - Starts Oracle, applies the migrations, starts the `persistence`, `processing`, `access` and `ingestion` APIs.
   - Waits until they are healthy.
   - First run pulls and builds images: a few minutes.
4. **Load real data:** `task dev:seed`
   - Loads ECB history since 2024-01-01 in two loads at two knowledge times.
   - Prints an `as_of` link between them.
   - Calls the ECB API (a few requests).
   - Less history: `task dev:seed START=2026-01-01`
5. **Start the explorer:** `task frontend:dev`, then open <http://localhost:5174> (or your `FRONTEND_PORT`).
   - Latest curve is shown first.
   - Pick another valid date, overlay dates, switch to one maturity's time series.
   - See what changed in the Changes view; check the data in the Quality view.
6. **Travel in time:** open the printed `?as_of=` link.
   - The explorer shows only what the platform knew then (latest curve about 20 business days older).
   - "Now" returns to today.
7. **See a correction:** `task dev:scenario:corrected-yield`
   - Plays publish, gap, bad value, late value, correction on the simulated curve `ecb-aaa-spot-sim`.
   - Pick that curve in the explorer to see quality flags, changes and each value's version history.

**API**

- <http://localhost:8000> (or your `ACCESS_PORT`)
- Example: `curl localhost:8000/v1/curves/ecb-aaa-spot/observations`

**Stop**

- `task dev:down` — keeps the data
- `task dev:reset` — removes it

&nbsp;

## Ports

Dev machines often run many containers, so no port is assumed free. Every host port is set in `.env`.

- `cp .env.example .env`, then change the values.
- Unset values fall back to the defaults below.
- Only the host side changes; containers still talk to each other on their internal ports.
- Use `task dev:*`: it loads `.env`. Bare `docker compose` does not.
- Setting `FRONTEND_PORT` also updates the API's allowed origin. Restart with `task dev:up`.

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

The maintainer's `.env` uses 6661–6670, in the table's order.

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
