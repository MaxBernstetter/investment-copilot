# Repository Layout

**All code lives under `src/`.** The repository root holds only entry points, tool configuration that tools expect at the root, and documentation.

```
src/
  contracts/               # only shared code: interface models + OpenAPI, versioned (own uv project)
    src/contracts/<service>/v1/
  services/
    ingestion/
    persistence/
      db/                  # Liquibase changelogs (admin/, core/), PL/SQL packages, utPLSQL tests (tests/)
      compose.yaml         # local Oracle Free + migrations for development
    processing/
      native/              # C++ kernel (pybind11)
    access/
  frontend/                # React + TypeScript SPA
  orchestration/           # Airflow (own uv project): DAGs plus small scheduling helpers
    dags/                  # DAG files (the Airflow DAG folder)
    src/orchestration/     # helpers the DAGs import, e.g. the TARGET calendar; no business logic
    tests/unit/
  observability/           # platform: OTel Collector, Prometheus, Loki, Tempo, Grafana provisioning
  deploy/                  # docker-compose, Caddyfile, env templates
  toolchain/               # repository-wide tasks: static analysis, git hooks
  scripts/                 # Bash scripts called by tasks
    tests/                 # bats tests for the scripts
docs/                      # Obsidian vault
  project/<NN-domain>/     # domain notes per domain (e.g. data sources, metrics, alerts)
.github/                   # thin CI workflows (provision devbox, call tasks); Dependabot
Taskfile.yml               # root task entry point; only includes component Taskfiles
devbox.json                # pinned toolchain
.pre-commit-config.yaml    # git hooks
.editorconfig
ARCHITECTURE.md
README.md
AGENTS.md
```

Every component directory has its own `Taskfile.yml` with the standard task names (see [[13-build-and-ci]]). This covers `src/services/<name>/`, `src/frontend/`, `src/orchestration/`, `src/contracts/` and `src/toolchain/`.

## Per-service structure (Python)

Every service is its own uv project with its own `pyproject.toml`, lockfile, Dockerfile and tests. Its only monorepo dependency is `src/contracts`.

```
src/services/<name>/
  pyproject.toml
  Taskfile.yml       # standard tasks: setup, fmt, lint, typecheck, test:*, build, image, run
  Dockerfile
  src/<name>/        # Python package (src layout inside the uv project)
    facade/          # published language: the only part other services see
      rest/          # FastAPI app (`api` process type)
      jobs/          # batch entrypoint (`job` process type)
      mapping.py     # contract ↔ domain translation
    application/     # use cases (one transaction each); defines ports
    domain/          # aggregates, value objects, domain rules: no I/O
    infrastructure/  # Oracle repositories (PL/SQL calls), clients to other services (anti-corruption)
    config.py        # settings from environment
  observability/
    dashboards/      # Grafana dashboards (JSON), provisioned by the platform
    alerts/          # alert rules (business + service level)
  tests/
    unit/            # domain and application, no I/O
    integration/     # adapters against Testcontainers
    contract/        # implementation vs. OpenAPI
```

Rules (enforced by import-linter, see [[11-service-design]]):
- Dependencies point inward: `facade` → `application` → `domain`. `infrastructure` implements ports from `application`.
- `domain` imports nothing from the other layers, from `contracts`, or from frameworks.
- Contract models appear only in `facade` and `infrastructure`. They are mapped to domain objects at those edges.
- Clients to other services live only in `infrastructure` and translate the other service's contract into this service's model.
