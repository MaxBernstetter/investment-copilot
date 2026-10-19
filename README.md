# yield-lens

**YieldLens** — an explorable, auditable and historically reproducible government bond yield dataset.

Yield curves feed risk calculations, valuation and investment decisions, but most tools show only the latest value and overwrite history. YieldLens keeps every value it has ever known:

- **Bitemporal history:** every value has a valid time (the date it applies to) and a knowledge time (when the platform learned it). Corrections add versions; nothing is overwritten.
- **Time travel:** every view and API call accepts an as-of time: "what did the platform show last Tuesday, based on what it knew then?"
- **Provenance:** every value links to its source delivery and ingestion run.

Today it loads the ECB euro area AAA spot curve (3M–30Y) daily, stores it bitemporally in Oracle, and serves it through a read-only API and a browser explorer with curve, overlay, time-series and time-travel views. More in [docs/idea/](docs/idea/) and [ARCHITECTURE.md](ARCHITECTURE.md).

## Try it locally

Prerequisites: Docker with Compose, and [devbox](https://www.jetify.com/devbox) (it provides `task`, Node and the other tools in pinned versions).

1. Open the toolchain shell: `devbox shell`
2. Start the stack: `task dev:up`
   Starts Oracle, applies the migrations and the `persistence` and `access` APIs, and waits until they are healthy. The first run pulls and builds images and takes a few minutes.
3. Load real data: `task dev:seed`
   Loads ECB history since 2024-01-01 in two loads at two knowledge times and prints an `as_of` link between them. This calls the ECB API (a few requests). Use `task dev:seed START=2026-01-01` for less history.
4. Start the explorer: `task frontend:dev`, then open <http://localhost:5173>
   You see the latest curve. Pick another valid date, overlay dates, or switch to the time series of one maturity.
5. Travel in time: open the printed `?as_of=` link
   The explorer shows only what the platform knew at that time: the latest curve is about 20 business days older. "Now" returns to today.

The API is at <http://localhost:8000>, e.g. `curl localhost:8000/v1/curves/ecb-aaa-spot/observations`.
Stop with `task dev:down` (keeps the data) or `task dev:reset` (removes it). Ports used: 1521, 8000, 8001, 5173.

## Develop

1. Clone, run `devbox shell`, then `task toolchain:setup` once to install the git hooks.
2. Set up the components you work on: `task <component>:setup`, with `access`, `contracts`, `frontend`, `ingestion`, `orchestration` or `persistence`. `task --list` shows every task.
3. Run the same checks as CI: `task <component>:lint`, `:typecheck`, `:test:unit`; `task toolchain:lint` runs all pre-commit hooks. Integration tests (`persistence`, `ingestion`) need Docker.
4. For agent-driven work with the GitHub board, export a `GITHUB_PAT` as described in [GitHub MCP connection](docs/development/02-github-mcp.md).

Before changing code, read:

- [AGENTS.md](AGENTS.md): working rules for humans and agents (board, PR size, worktrees, subagents).
- [Development principles](docs/development/principles/README.md) and the Definition of done.
- [Task management](docs/development/01-task-management.md): issues, board and pull requests.
- [Build, tasks and CI](docs/architecture/13-build-and-ci.md): Taskfiles, workflows, required checks.
- [Agent harness](docs/development/03-agent-harness.md): which model does what in agentic development.

The `docs/` folder is an Obsidian vault; start at [docs/README.md](docs/README.md).
