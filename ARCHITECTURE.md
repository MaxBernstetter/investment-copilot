# Architecture

YieldLens is a monorepo of independently deployable services, one per domain (bounded context). Services share nothing but versioned interface models and talk only through their published interfaces. Details live in [docs/architecture/](docs/architecture/README.md).

## Principles

- **One service per bounded context:** its own codebase, container, tests and Oracle schema.
- **Strict separation:** no cross-imports and no cross-schema access. The only shared code is `contracts/`, which holds the interface models.
- **Contract-first interfaces:** versioned REST/OpenAPI; bulk data via streamed Apache Arrow.
- **Every service is robust, idempotent, transparent, performant and elastic:**
  - It has a thin public facade over an internal domain model (DDD).
  - It runs as an `api` process plus ephemeral `job` containers, so it is cheap when idle and scales out for spikes.
  - It exposes its own business data, alerts and telemetry.
- **Insert-only, bitemporal core:** nothing is overwritten, and everything is reproducible as of any knowledge time.
- **Gated, replayable pipeline:**
  - Raw → core → marts, with validation gates between stages.
  - Marts are refreshed by write–audit–publish (build, validate, then swap in).
  - Everything that shapes data is versioned, so any range can be replayed from raw.
- **Thin orchestration:** Airflow schedules and sequences; business logic lives in the services.
- **Built to scale 100× without redesign; deployed free for the demo.**

## Services

| Service | Responsibility | Data | Tech |
|---|---|---|---|
| `ingestion` | Source adapters, normalization, raw payloads, scenario injection, source runs | `ING` | Python |
| `persistence` | Bitemporal core: versions, as-of retrieval, value lineage, knowledge-state diffs | `CORE` | Oracle, PL/SQL, Python |
| `processing` | Quality rules, derived curves and measures, recalculation and impact, marts, anomalies | `PROC` | Python, QuantLib, C++ (pybind11), scikit-learn |
| `access` | Public read-only REST API, cross-service lineage, grounded Q&A | – | FastAPI |
| `frontend` | Explorer and operations UI, talks only to `access` | – | React, TypeScript, Plotly.js |

Platform: `orchestration/` (Apache Airflow), `observability/` (OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana), `contracts/` (shared interface models), `deploy/` (Docker Compose, Caddy).

## Flow

```
 public sources
      │
 ┌────▼─────┐   ┌─────────────┐   ┌────────────┐   ┌──────────┐   ┌──────────────┐
 │ingestion │──▶│ persistence │◀─▶│ processing │──▶│  access  │──▶│ frontend SPA │
 └────┬─────┘   └──────┬──────┘   └─────┬──────┘   └──────────┘   │ GitHub Pages │
      │                │                │                         └──────────────┘
      └── metrics · logs · traces (OTel) ──▶ observability stack (Grafana)
              ▲ Airflow orchestrates every stage through the service interfaces
```

## Deployment

The frontend is a static build on **GitHub Pages**. The backend (Oracle Free 23ai, the services, Airflow, the observability stack and Caddy) runs as one Docker Compose stack on an **OCI Always Free** ARM VM. The same stack runs locally.

## Further reading

1. [Context map](docs/architecture/01-context-map.md)
2. [Interfaces & contracts](docs/architecture/02-interfaces-and-contracts.md)
3. [Data architecture](docs/architecture/03-data-architecture.md)
4. [Orchestration](docs/architecture/04-orchestration.md)
5. [Tech stack](docs/architecture/05-tech-stack.md)
6. [Repository layout](docs/architecture/06-repository-layout.md)
8. [Scalability](docs/architecture/08-scalability.md)
9. [Deployment](docs/architecture/09-deployment.md)
10. [Observability & transparency](docs/architecture/10-observability.md)
11. [Service design](docs/architecture/11-service-design.md)
12. [Data pipeline](docs/architecture/12-data-pipeline.md)
13. [Architecture decision records](docs/architecture/adr/)

How to build and ship each piece: [development principles](docs/development/principles/README.md).
