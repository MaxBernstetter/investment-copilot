# Twelve-Factor App

Every YieldLens service follows the [Twelve-Factor App](https://12factor.net/) methodology. The table states what each factor means **in this project**.

| # | Factor | Rule in YieldLens |
|---|---|---|
| I | Codebase | One monorepo; each service is a separately built and deployed app inside it. |
| II | Dependencies | Declared and locked per service (`pyproject.toml` + `uv.lock`, `package.json` + lockfile). Nothing relies on system-wide packages. |
| III | Config | Everything that differs between environments comes from environment variables, validated at startup (pydantic-settings). No config files per environment in the repo; no secrets in code. |
| IV | Backing services | Oracle, other services, the OTel Collector are attached resources addressed by URL/credentials from config. Swapping one needs no code change. |
| V | Build, release, run | CI builds an immutable image per commit; release = image + config; run = `docker compose up`. No changes to running containers. |
| VI | Processes | Services are stateless. All state lives in Oracle; nothing persists in memory or on local disk between requests. |
| VII | Port binding | Each service is self-contained and exports HTTP on a configured port; Caddy only routes. |
| VIII | Concurrency | Scale by running more processes or containers, not bigger ones. Work is split into chunks (date ranges) to run in parallel. |
| IX | Disposability | Fast startup, graceful shutdown on `SIGTERM`, idempotent operations so that a killed task can simply rerun. |
| X | Dev/prod parity | The same Compose stack and images locally and live; same Oracle version. |
| XI | Logs | Structured JSON to stdout as an event stream; the platform collects and routes it (see `docs/architecture/10-observability.md`). |
| XII | Admin processes | One-off tasks (migrations, backfills, scenario injection) run as versioned commands or DAGs against the same release, never by hand in a shell. |

## Checks when planning a piece

- Which configuration does it need, and is it all from environment variables?
- Does it keep any state outside Oracle? If yes, redesign.
- Can it be killed at any moment and rerun safely?
- Does it behave the same locally and live?
