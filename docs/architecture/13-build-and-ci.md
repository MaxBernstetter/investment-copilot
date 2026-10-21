# Build, Tasks and CI

Every task (format, lint, test, build, run, deploy) is run the same way by developers, agents and CI, and **every CI run can be reproduced locally**. See [[0014-taskfile-and-local-first-ci]] and [[0015-pre-commit-hooks]].

## Building blocks

| Layer | Tool | Role |
|---|---|---|
| Toolchain | devbox (Nix) | Pins every tool and version (task, uv, Python, Node, bats, …); identical locally and in CI |
| Task interface | go-task (`Taskfile.yml`) | The standardized entry point for every task |
| Logic | Bash scripts in `src/scripts/` | Anything beyond calling a command; linted and tested |
| Commit-time checks | pre-commit | Fast, file-scoped checks before a commit |
| CI | GitHub Actions | Thin wrapper: provision devbox, call tasks |

## Taskfiles

- **Structure:** a root `Taskfile.yml` includes one Taskfile per component under `src/` (`src/services/<name>/`, `src/frontend/`, `src/orchestration/`, `src/contracts/`, `src/toolchain/`), namespaced as `<component>:<task>`.
- **Standard task names:** every component implements the same set, as far as it applies:
  - `setup`, `fmt`, `lint`, `typecheck`
  - `test:unit`, `test:integration`, `test:contract`
  - `build`, `image`, `run`

  This lets CI and humans treat components uniformly.
- **Glue only:** each `cmd` is a single command or binary call, or a call to another task. Not allowed in a Taskfile:
  - pipes, loops, conditionals, command substitution
  - multi-line inline shell
- **Logic goes into scripts:** if a task needs more than a single command, the logic lives in a script under `src/scripts/` and the task calls it.
- **Self-documenting:** every public task has a `desc`; helper tasks are `internal: true`. `task --list` is the menu.
- **Parameters:** passed as task variables (`task <x> VAR=…`), mapped one-to-one to script or command arguments.
- **Incremental:** `sources`/`generates` are used where they avoid redundant work (e.g. client generation, image builds).

## Scripts

- **Language:** Bash, starting with `set -euo pipefail`. One purpose per script.
- **Header:** usage, arguments and every environment variable it reads. No hidden inputs.
- **Exit codes:** `0` success, `1` check failed, `2` usage or setup error.
- **Quality:**
  - Formatted with shfmt and linted with ShellCheck (pre-commit and CI).
  - Tested with bats; tests live in `src/scripts/tests/` and run in CI like any other code.
- **Escalation:** if a script outgrows Bash (complex parsing, data handling), it becomes a small Python CLI with tests instead.
- **Analysis scripts:** read-only, manually run analyses that document how a decision was derived may be a single standard-library Python file (formatted and linted with ruff), e.g. `src/scripts/plausibility_thresholds.py` for [[01-plausibility-thresholds]]. They are not run in CI.

## Versioning

- **SemVer:** the frontend (`src/frontend/package.json`) follows [Semantic Versioning](https://semver.org/). It stays on `0.x` during the phases of the project.
- **Deliberate bumps:** the version is changed by hand in a pull request, never by a build. A release PR states the new version.
- **Shown in the app:** the footer shows `v{version} · {commit}`. The version comes from `package.json` at build time (`vite.config.ts`); the commit is `VITE_COMMIT`, which the `frontend:build` task sets from `git rev-parse --short HEAD` (`dev` when git is unavailable, e.g. in `frontend:dev`).

## CI

- **Thin workflows:** a job checks out the repo, provisions the devbox toolchain, restores caches, and calls tasks. No tool installs, scripts or logic in workflow YAML.
- **Local parity:** every CI step is `devbox run -- task <component>:<task>`, so the exact step can be run locally with the same command and tool versions. `act` is optional, for debugging workflow wiring only.
- **Path filters:** on pushes to `main`, a component's workflow runs only when its files change. A change in `src/contracts/` runs every consumer.
- **Pull requests are not path-filtered:** every component workflow runs on every pull request, so each required check reports on every PR (see [Required checks](#required-checks)).
- **Services in tests:** integration tests start real dependencies via Testcontainers (Oracle Free, HTTP stubs), both locally and in CI. They don't rely on CI service containers.
- **Hooks are re-checked:** CI runs `pre-commit run --all-files`, so skipping hooks locally cannot bypass them.
- **Delivery:** image builds and deployments are tasks as well. The deploy workflow only calls them with environment-specific secrets (see the delivery and security principles).
- **Workflow security:**
  - Actions are pinned to full commit SHAs (version in a trailing comment); Dependabot keeps them current.
  - Token permissions are least-privilege (`contents: read` by default), and checkout uses `persist-credentials: false`.
  - Workflows are checked by actionlint and zizmor.

### Current workflows

| Workflow | Trigger | Runs | Local equivalent |
|---|---|---|---|
| `static-analysis.yml` | Push to `main`, pull requests, manual | `task toolchain:lint`: all pre-commit hooks on all files | `devbox run -- task toolchain:lint` |
| `contracts.yml` | Pull requests; pushes to `main` changing `src/contracts/`, the root Taskfile or devbox; manual | `contracts:` `setup`, `lint`, `typecheck`, `test:unit` | `devbox run -- task contracts:<task>` |
| `persistence.yml` | Pull requests; pushes to `main` changing `src/services/persistence/`, `src/contracts/`, the root Taskfile or devbox; manual | `persistence:` `setup`, `lint`, `typecheck`, `test:unit`; `test:integration` in its own job | `devbox run -- task persistence:<task>` |
| `ingestion.yml` | Pull requests; pushes to `main` changing `src/services/ingestion/`, `src/contracts/`, the root Taskfile or devbox; manual | `ingestion:setup`, `ingestion:lint`, `ingestion:typecheck`, `ingestion:test:unit` | `devbox run -- task ingestion:<task>` |
| `orchestration.yml` | Pull requests; pushes to `main` changing `src/orchestration/`, the root Taskfile or devbox; manual | `orchestration:setup`, `orchestration:lint`, `orchestration:typecheck`, `orchestration:test:unit` | `devbox run -- task orchestration:<task>` |
| `processing.yml` | Pull requests; pushes to `main` changing `src/services/processing/`, `src/contracts/`, the root Taskfile or devbox; manual | `processing:` `setup`, `lint`, `typecheck`, `test:unit`; `test:integration` in its own job | `devbox run -- task processing:<task>` |
| `access.yml` | Pull requests; pushes to `main` changing `src/services/access/`, `src/contracts/`, the root Taskfile or devbox; manual | `access:` `setup`, `lint`, `typecheck`, `test:unit` | `devbox run -- task access:<task>` |
| `frontend.yml` | Pull requests; pushes to `main` changing `src/frontend/`, `src/contracts/openapi/access/`, the root Taskfile or devbox; manual | `frontend:` `setup`, `audit`, `lint`, `typecheck`, `test:unit`, `build`, `size`; job `frontend: e2e` runs `frontend:e2e` after `build` in `mcr.microsoft.com/playwright:v1.55.1-noble` | `devbox run -- task frontend:<task>` |
| `pages.yml` | Pushes to `main` changing `src/frontend/`, `src/contracts/openapi/access/`, the workflow, the root Taskfile or devbox; manual | Job `configured` checks that `vars.VITE_ACCESS_URL` is set on the `github-pages` Environment; jobs `build` (`frontend:build:pages`, then the Pages artifact) and `deploy` (`actions/deploy-pages`) are skipped until it is set | `devbox run -- task frontend:build:pages` |
| `e2e.yml` | Pull requests; pushes to `main` changing `src/`, the workflow, the root Taskfile or devbox; manual | `dev:reset`, `dev:up`, `dev:e2e` (the corrected-yield test on a fresh stack), `dev:reset` again at the end | `devbox run -- task dev:e2e` after `dev:reset` and `dev:up` |
| `images.yml` | Pull requests, pushes to `main` (no path filter), manual | PRs and manual: `<service>:image` for amd64 and arm64 (build only), then `image` and `image:scan`. Pushes to `main`: `image`, `image:scan`, then `image` with `OUTPUT=type=registry` for amd64 and arm64 | `devbox run -- task <service>:image` and `devbox run -- task <service>:image:scan` |

### Images

- Container images are named `ghcr.io/maxbernstetter/yield-lens-<service>` for `persistence`, `access`, `ingestion` and `processing`, tagged only with the full 40-character commit SHA.
- Published images are multi-arch (`linux/amd64` and `linux/arm64`); CI uses Docker Buildx with QEMU for arm64.
- Pull requests build and scan images but never push; only the `publish` job on pushes to `main` gets `packages: write` and pushes to GHCR.
- There is no path filter: every commit on `main` gets a complete set of four images under the same SHA so deploys can pin any commit with one tag.
- After the amd64 image is built locally in Docker, Trivy scans it using `trivy.yaml` at the repository root (fixable HIGH and CRITICAL vulnerabilities fail the job). Accepted exceptions go in `.trivyignore` with a reason.
- The `images: build and scan <service>` checks are not required on `main` yet; add them to the ruleset after they have been green for a while.
- Locally, `task <service>:image` builds the host platform by default. A multi-platform build needs a `docker-container` builder (`docker buildx create --use`) and binfmt/QEMU support.

### Required checks

Branch protection needs stable check names. Each job below has a fixed `name:` that is its check name on pull requests:

- `pre-commit` (`static-analysis.yml`)
- `access: lint, types, unit tests`
- `contracts: lint, types, unit tests`
- `frontend: lint, types, unit tests, build`
- `frontend: e2e` (`frontend.yml`)
- `ingestion: lint, typecheck, unit tests`
- `ingestion: integration tests`
- `orchestration: lint, typecheck, unit tests`
- `persistence: lint, types, unit tests`
- `persistence: integration tests`
- `processing: integration tests`
- `processing: lint, types, unit tests`
- `e2e: corrected yield` (`e2e.yml`)

Pull-request runs are not path-filtered, so every required check reports on every pull request, including PRs that touch only docs. Path filters apply only to pushes to `main`. A job skipped by a filter would otherwise leave a required check pending forever.

A repository admin must add these names as required status checks in the `main` ruleset. Renaming a job changes its check name, so update the ruleset in the same change.

### Current tasks

The root `Taskfile.yml` only includes components. Repository-wide tooling lives in `src/toolchain/Taskfile.yml` (namespace `toolchain`, run from the repository root):

| Task | Does |
|---|---|
| `toolchain:setup` | Install the git hooks and their environments |
| `toolchain:lint` | All static analysis: every pre-commit hook on all files (used by CI) |
| `toolchain:update` | Update pinned hook versions |

The local development stack (Oracle, the `CORE`, `ING` and `PROC` migrations, persistence, processing, access and ingestion apis, the ingestion job) lives in `src/deploy/` (namespace `dev`, run from that directory):

| Task | Does |
|---|---|
| `dev:up` | Start Oracle, apply the `CORE`, `ING` and `PROC` migrations and start the persistence, processing, access and ingestion apis; waits until healthy (idempotent) |
| `dev:down` | Stop the local stack (keeps its data) |
| `dev:reset` | Remove the local stack and its data |
| `dev:obs:up` | Start the observability profile (collector, Prometheus, Tempo, Grafana) on top of `dev:up` and restart the apis with `OTEL_*` (opt-in) |
| `dev:obs:down` | Stop the observability profile (keeps its data) and restart the apis without `OTEL_*` |
| `dev:obs:smoke` | Check the observability profile: `OTEL_*` wiring, Grafana datasources, OTLP metrics and a trace via telemetrygen (after `dev:obs:up`) |
| `dev:seed` | Load ECB history from `START` (default `2024-01-01`) in two steps with a knowledge time between them, via `src/scripts/dev-seed.sh` (live ECB calls; manual only) |
| `dev:check-quality` | Run `processing-check-quality` for `CURVE`, `FROM` and `TO` in the `processing-job` container |
| `dev:scenario:corrected-yield` | Run the corrected-yield scenario and check quality for `ecb-aaa-spot-sim` on 2026-10-05..2026-10-08 |
| `dev:e2e` | End-to-end corrected-yield test (`src/e2e`) against the running stack; run `dev:reset` and `dev:up` first |

Python components (`contracts`, `persistence`, `ingestion`, `orchestration`, `access`, `processing`) implement `setup`, `fmt`, `lint`, `typecheck` and `test:unit`; services add `test:integration` and `run` where they need them. The four deployable services (`persistence`, `access`, `ingestion`, `processing`) also implement `image` and `image:scan`, with task variables `IMAGE`, `TAG`, `PLATFORMS` and `OUTPUT`. `persistence` also has `db:start`, `db:migrate`, `db:stop` and `db:reset` for its local Oracle database (see [[02-persistence-service]]); `ingestion` has `db:migrate` for its `ING` schema in that database (see [[04-raw-deliveries]]); `processing` has `db:migrate` for its `PROC` schema. `orchestration` also has `pools:import`, which creates the Airflow pools from `pools.json` (see [[04-daily-schedule]]).

The frontend (`src/frontend/`, namespace `frontend`) is an npm project and implements `setup`, `audit`, `fmt`, `lint`, `typecheck`, `test:unit`, `build`, `build:pages` (the Pages bundle, needs `VITE_ACCESS_URL`), `size` (the bundle budget, after `build`), `e2e`, `e2e:update` and `dev` (see [[01-frontend]]).

Each service has its own Taskfile, included as `<service>:<task>` and run from the service directory (Python services use `uv run --locked`):

| Task | Does |
|---|---|
| `ingestion:setup` | Create the virtual environment from `uv.lock` |
| `ingestion:fmt` | Format with ruff and apply safe lint fixes |
| `ingestion:lint` | ruff lint and format check, import-linter layer rules |
| `ingestion:typecheck` | mypy strict on sources and tests |
| `ingestion:test:unit` | Unit tests (no I/O, no live sources) |
| `ingestion:test:integration` | Integration tests against Oracle Free (Testcontainers), including the utPLSQL suites of `ING` |
| `ingestion:db:migrate` | Apply the `ING` changelogs to the local database started by `persistence:db:start` |
| `ingestion:load:ecb:daily`, `ingestion:load:ecb:history` | Manual ECB loads against a running persistence api (see [[03-ecb-load]]); they call the live ECB API and never run in CI |
| `ingestion:load:ecb:replay` | Manual replay of stored ECB deliveries (`FROM`, `TO`: fetch days) against a running persistence api; never calls the ECB (see [[04-raw-deliveries#Replay]]) |
| `ingestion:run` | Run the ingestion api locally on port 8003 against the ING database |
| `ingestion:openapi` | Export the ingestion OpenAPI document to `src/contracts/openapi/ingestion/v1.json` (committed; the unit test fails when it is stale) |
| `access:openapi` | Export the access OpenAPI document to `src/contracts/openapi/access/v1.json` (committed; the unit test fails when it is stale) |

## Pre-commit hooks

Commit-time hooks are fast and file-scoped. Slow or cross-cutting checks (type checks, tests, contract tests) run as tasks and in CI.

| Hook | Purpose |
|---|---|
| pre-commit-hooks | Whitespace, final newline, LF line endings, YAML/JSON/TOML syntax, merge conflicts, case conflicts, shebang/executable consistency, large files, private keys |
| gitleaks | Secret scanning |
| ShellCheck, shfmt | Shell lint and format |
| ruff | Python lint (`ruff-check`) and format (`ruff-format`); configuration per uv project in its `pyproject.toml` |
| actionlint | GitHub Actions workflow lint |
| zizmor | GitHub Actions security analysis (unpinned actions, credential persistence, template injection, permissions) |

Hooks are added per language as components appear: ESLint/Prettier (frontend), SQL linting for Liquibase/PL/SQL. Vendored agent skills and generated lockfiles are excluded.

Setup: `task toolchain:setup` once per clone; `task toolchain:lint` runs every hook.
