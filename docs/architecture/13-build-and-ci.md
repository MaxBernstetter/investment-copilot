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

## CI

- **Thin workflows:** a job checks out the repo, provisions the devbox toolchain, restores caches, and calls tasks. No tool installs, scripts or logic in workflow YAML.
- **Local parity:** every CI step is `devbox run -- task <component>:<task>`, so the exact step can be run locally with the same command and tool versions. `act` is optional, for debugging workflow wiring only.
- **Path filters:** select which components' tasks run. A change in `src/contracts/` runs every consumer.
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
| `contracts.yml` | Changes in `src/contracts/`, the root Taskfile or devbox; manual | `contracts:` `setup`, `lint`, `typecheck`, `test:unit` | `devbox run -- task contracts:<task>` |
| `persistence.yml` | Changes in `src/services/persistence/`, `src/contracts/`, the root Taskfile or devbox; manual | `persistence:` `setup`, `lint`, `typecheck`, `test:unit`; `test:integration` in its own job | `devbox run -- task persistence:<task>` |
| `ingestion.yml` | Push to `main` and pull requests touching `src/services/ingestion/`, `src/contracts/`, the root Taskfile or devbox; manual | `ingestion:setup`, `ingestion:lint`, `ingestion:typecheck`, `ingestion:test:unit` | `devbox run -- task ingestion:<task>` |

### Current tasks

The root `Taskfile.yml` only includes components. Repository-wide tooling lives in `src/toolchain/Taskfile.yml` (namespace `toolchain`, run from the repository root):

| Task | Does |
|---|---|
| `toolchain:setup` | Install the git hooks and their environments |
| `toolchain:lint` | All static analysis: every pre-commit hook on all files (used by CI) |
| `toolchain:update` | Update pinned hook versions |

Python components (`contracts`, `persistence`, `ingestion`) implement `setup`, `fmt`, `lint`, `typecheck` and `test:unit`; services add `test:integration` and `run` where they need them. `persistence` also has `db:start`, `db:migrate`, `db:stop` and `db:reset` for its local Oracle database (see [[02-persistence-service]]).

Each service has its own Taskfile, included as `<service>:<task>` and run from the service directory (Python services use `uv run --locked`):

| Task | Does |
|---|---|
| `ingestion:setup` | Create the virtual environment from `uv.lock` |
| `ingestion:fmt` | Format with ruff and apply safe lint fixes |
| `ingestion:lint` | ruff lint and format check, import-linter layer rules |
| `ingestion:typecheck` | mypy strict on sources and tests |
| `ingestion:test:unit` | Unit tests (no I/O, no live sources) |
| `ingestion:load:ecb:daily`, `ingestion:load:ecb:history` | Manual ECB loads against a running persistence api (see [[03-ecb-load]]); they call the live ECB API and never run in CI |

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
