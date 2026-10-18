# Architecture

YieldLens is a monorepo of independently deployable services, one per domain (bounded context). Services share nothing but versioned interface models and talk only through their published interfaces. This page is the overview; the details and all decisions live in [docs/architecture/](docs/architecture/README.md).

## Principles

- **One service per bounded context:** its own codebase, container, tests and Oracle schema.
- **Strict separation:** no cross-imports and no cross-schema access. The only shared code is `contracts/`, which holds the interface models.
- **Contract-first interfaces:** versioned REST/OpenAPI; bulk data via streamed Apache Arrow.
- **Every service is robust, idempotent, transparent, performant and elastic:**
  - It has a thin public facade over an internal domain model (DDD).
  - It runs as an `api` process plus ephemeral `job` containers, so it is cheap when idle and scales out for spikes.
  - It exposes its own business data (runs, lineage, quality), alerts and telemetry.
- **Insert-only, bitemporal core:** nothing is overwritten, and everything is reproducible as of any knowledge time.
- **Gated, replayable pipeline:**
  - Raw → core → marts, with validation gates between stages. Bad data is quarantined, never silently dropped.
  - Marts are refreshed by write–audit–publish (build, validate, then swap in).
  - Everything that shapes data is versioned, so any range can be replayed from raw.
- **Thin orchestration:** Airflow schedules and sequences; business logic lives in the services.
- **Local-first CI:**
  - Every task runs through `task` with a devbox-pinned toolchain.
  - CI only calls those tasks, so every CI run is reproducible locally.
  - Logic lives in tested scripts; pre-commit hooks guard every commit.
- **Built to scale 100× without redesign; deployed free for the demo.**

## Services

| Service | Responsibility | Data | Tech |
|---|---|---|---|
| `ingestion` | Source adapters and source contracts, schema-drift checks and quarantine, revision lookback, normalization, raw payloads, scenario injection, source runs | `ING` | Python, Polars, Pandera |
| `persistence` | Bitemporal core: versions, as-of retrieval, curve definitions, value lineage, knowledge-state diffs | `CORE` | Oracle, PL/SQL, Python |
| `processing` | Quality rules and validation gates, derived curves and measures, recalculation and impact, marts (write–audit–publish), anomalies | `PROC` | Python, QuantLib, C++ (pybind11), scikit-learn |
| `access` | Public read-only REST API, cross-service lineage, response caching, grounded Q&A | – | FastAPI |
| `frontend` | Explorer and operations UI, talks only to `access` | – | React, TypeScript, Plotly.js |

All code lives under `src/`: the services (`src/services/<name>/`), the frontend, and these platform parts, which hold no domain logic:

- `src/contracts/`: shared interface models and OpenAPI documents, versioned
- `src/orchestration/`: Apache Airflow (+ Postgres metadata DB), OpenLineage events
- `src/observability/`: OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana
- `src/deploy/`: Docker Compose, Caddy
- `src/toolchain/`: repository-wide tasks (static analysis, git hooks)
- `src/scripts/`: Bash scripts called by tasks

The repository root keeps only entry points and tool config: `Taskfile.yml`, `devbox.json`, `.pre-commit-config.yaml`, `.github/`, `docs/`.

## Flow

```
 public sources
      │
 ┌────▼──────┐  gate  ┌─────────────┐        ┌────────────┐  gate + WAP  ┌──────────┐   ┌──────────────┐
 │ ingestion │──────▶ │ persistence │ ◀────▶ │ processing │ ───marts───▶ │  access  │──▶│ frontend SPA │
 │ raw (ING) │        │ core (CORE) │        │ marts(PROC)│              └──────────┘   │ GitHub Pages │
 └───────────┘        └─────────────┘        └────────────┘                             └──────────────┘
   every service ── metrics · logs · traces (OTel) ──▶ observability stack (Grafana)
   every service ── runs · lineage · alerts (transparency interface) ──▶ access
   Airflow orchestrates every stage through the service interfaces and starts `job` containers
```

## Deployment

The frontend is a static build on **GitHub Pages**. The backend (Oracle Free 23ai, the services, Airflow, the observability stack and Caddy) runs as one Docker Compose stack on an **OCI Always Free** ARM VM; only `access` is public. The same stack runs locally. Oracle is backed up daily with Data Pump to OCI Object Storage.

## Further reading

- [Architecture index](docs/architecture/README.md): all architecture notes and decision records (ADRs)
- [Development principles](docs/development/principles/README.md): how to build and ship each piece
