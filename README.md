# yield-lens

**YieldLens** — an explorable, auditable and historically reproducible government bond yield dataset.

Yield curves feed risk calculations, valuation and investment decisions, but most tools show only the latest value and overwrite history. YieldLens keeps every value it has ever known:

- **Bitemporal history:** every value has a valid time (the date it applies to) and a knowledge time (when the platform learned it). Corrections add versions; nothing is overwritten.
- **Time travel:** every view and API call accepts an as-of time: "what did the platform show last Tuesday, based on what it knew then?"
- **Provenance:** every value links to its source delivery and ingestion run.

Today it loads the ECB euro area AAA spot curve (3M–30Y), stores it bitemporally in Oracle, checks every value against plausibility and completeness rules, and serves it through a read-only API and a browser explorer. The explorer has curve, overlay, time-series, changes and quality views, quality badges with explanations on every flagged value, a version history per value, and time travel. Daily loads run in Airflow (optional locally, see below). More in [docs/idea/](docs/idea/) and [ARCHITECTURE.md](ARCHITECTURE.md).

## Try it locally

Prerequisites: Docker with Compose, and [devbox](https://www.jetify.com/devbox) (it provides `task`, Node and the other tools in pinned versions).

1. Open the toolchain shell: `devbox shell`
2. Start the stack: `task dev:up`. Starts Oracle, applies the migrations, starts the `persistence`, `processing`, `access` and `ingestion` APIs, and waits until they are healthy. The first run pulls and builds images and takes a few minutes.
3. Load real data: `task dev:seed`. Loads ECB history since 2024-01-01 in two loads at two knowledge times and prints an `as_of` link between them. This calls the ECB API (a few requests). Use `task dev:seed START=2026-01-01` for less history.
4. Start the explorer: `task frontend:dev`, then open <http://localhost:5174>. You see the latest curve. Pick another valid date, overlay dates, switch to the time series of one maturity, see what changed in the Changes view, or check the data in the Quality view.
5. Travel in time: open the printed `?as_of=` link. The explorer shows only what the platform knew at that time: the latest curve is about 20 business days older. "Now" returns to today.
6. See a correction: `task dev:scenario:corrected-yield` plays a scenario on the simulated curve `ecb-aaa-spot-sim` (publish, gap, bad value, late value, correction). Pick that curve in the explorer to see the quality flags, the changes and each value's version history.

The API is at <http://localhost:8000>, e.g. `curl localhost:8000/v1/curves/ecb-aaa-spot/observations`.
Stop with `task dev:down` (keeps the data) or `task dev:reset` (removes it). Ports used: 1521, 8000, 8001, 8002, 8003, 5174. To serve the explorer on another port, set `FRONTEND_PORT` for both `task dev:up` and `task frontend:dev`, so the API allows that origin.

Optional Airflow UI: `task dev:airflow:up`, then <http://127.0.0.1:8088>. Sign in as `airflow` / `airflow` — that admin user is created by the `airflow-init` service (`_AIRFLOW_WWW_USER_*` in `src/deploy/compose.yaml`), not an Airflow default. Stop with `task dev:airflow:down`. The UI uses host port 8088 (8080 is often already taken).

Optional observability: `task dev:obs:up` starts the OpenTelemetry Collector, Prometheus (<http://127.0.0.1:9090>), Tempo (port 3200) and Grafana (<http://127.0.0.1:3300>, user `admin`, password `LocalGrafana_1` unless `GRAFANA_ADMIN_PASSWORD` is set) with the processing dashboard and the `quality-warn` alert. `task dev:obs:smoke` checks the wiring, `task dev:obs:firing-check` shows the alert firing and clearing, and `task dev:obs:down` stops it.

## Develop

1. Clone, run `devbox shell`, then `task toolchain:setup` once to install the git hooks.
2. Set up the components you work on: `task <component>:setup`, with `access`, `contracts`, `frontend`, `ingestion`, `orchestration`, `persistence` or `processing`. `task --list` shows every task.
3. Run the same checks as CI: `task <component>:lint`, `:typecheck`, `:test:unit`; `task toolchain:lint` runs all pre-commit hooks. Integration tests (`persistence`, `ingestion`, `processing`) need Docker.
4. For agent-driven work with the GitHub board, export a `GITHUB_PAT` as described in [GitHub MCP connection](docs/development/02-github-mcp.md).

Before changing code, read:

- [AGENTS.md](AGENTS.md): working rules for humans and agents (board, PR size, worktrees, subagents).
- [Development principles](docs/development/principles/README.md) and the Definition of done.
- [Task management](docs/development/01-task-management.md): issues, board and pull requests.
- [Build, tasks and CI](docs/architecture/13-build-and-ci.md): Taskfiles, workflows, required checks.
- [Agent harness](docs/development/03-agent-harness.md): which model does what in agentic development.

The `docs/` folder is an Obsidian vault; start at [docs/README.md](docs/README.md).
