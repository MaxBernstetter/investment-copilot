# Access Service

The `access` service (`src/services/access/`) is the public, read-only API of YieldLens. It is the only service the frontend calls. This first slice is the skeleton: it exposes liveness and readiness and relays persistence readiness; the read endpoints land in later issues.

## Interface (`api` process)

| Method and path | Purpose | Responses |
|---|---|---|
| `GET /health` | Liveness: the process is up | `200 {"status": "ok"}` |
| `GET /ready` | Readiness: the persistence service answers `200` on its own `/ready` | `200 {"status": "ready"}`, `503 {"status": "unavailable"}` (also when persistence is unreachable) |

- CORS: only `GET` is allowed, from the origins in `ACCESS_CORS_ORIGINS`. Other origins get no `Access-Control-Allow-Origin` header.

## Layers

| Package | Content |
|---|---|
| `access.domain` | Reserved for the read model (empty for now) |
| `access.application` | Reserved for the use cases (empty for now) |
| `access.infrastructure` | `PersistenceClient`: asks persistence for readiness; any transport error counts as not ready |
| `access.facade` | FastAPI app, CORS, health and readiness routes |
| `access.api` | Composition root of the `api` process |

import-linter enforces that dependencies point inward and that domain and application import no frameworks, HTTP clients or contracts.

## Configuration

Environment variables, validated at startup (pydantic-settings):

| Variable | Default | Meaning |
|---|---|---|
| `ACCESS_PERSISTENCE_URL` | – (required) | Base URL of the persistence api, e.g. `http://localhost:8001` |
| `ACCESS_PERSISTENCE_TIMEOUT_SECONDS` | `10` | Timeout of one call to persistence |
| `ACCESS_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins allowed to call the API (the Vite dev server by default) |

## Running locally

```sh
devbox run -- task access:setup     # virtual environment
devbox run -- task persistence:run  # persistence api on http://localhost:8001 (for readiness)
devbox run -- task access:run       # access api on http://localhost:8000
```

`PORT` changes the port of `access:run`. Logs are JSON lines (`log_config.json`).

## Tests

- `devbox run -- task access:test:unit`: REST routes, CORS, the persistence client (with `httpx.MockTransport`), configuration and the log configuration. No network.
- `devbox run -- task access:lint`, `access:typecheck`: ruff, import-linter, mypy (strict).

## Not yet in place

- Rate limiting
- Caching and ETag support
- Transparency (lineage and run status for the frontend)
- Metrics
- Traces
