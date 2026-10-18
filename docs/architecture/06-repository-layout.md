# Repository Layout

```
contracts/                 # only shared code: interface models + OpenAPI, versioned
  <service>/v1/
services/
  ingestion/
  persistence/
    db/                    # Liquibase changelogs, PL/SQL packages, utPLSQL tests
  processing/
    native/                # C++ kernel (pybind11)
  access/
frontend/                  # React + TypeScript SPA
orchestration/
  dags/
observability/             # platform: OTel Collector, Prometheus, Loki, Tempo, Grafana provisioning
deploy/                    # docker-compose, Caddyfile, env templates
docs/                      # Obsidian vault
ARCHITECTURE.md
```

## Per-service structure (Python)

Every service is its own uv project with its own `pyproject.toml`, lockfile, Dockerfile and tests. Its only monorepo dependency is `contracts`.

```
services/<name>/
  pyproject.toml
  Dockerfile
  src/<name>/
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
