# Tech Stack

## Choices per layer

| Layer | Technology |
|---|---|
| Database | Oracle Database Free 23ai, PL/SQL, Liquibase, utPLSQL |
| DB access | python-oracledb (thin mode) |
| Services | Python 3.13, FastAPI, Pydantic v2 (pydantic-settings for config), httpx (outbound HTTP), uv |
| Bulk data | Apache Arrow (pyarrow), Polars |
| Data validation | Pandera (schema and type checks at ingestion); custom domain rules in processing |
| Lineage | OpenLineage (Airflow provider, Python client); Marquez optional |
| Backup | Oracle Data Pump → OCI Object Storage |
| Curve maths | QuantLib (Python), C++ kernel via pybind11 + scikit-build-core |
| ML | scikit-learn (anomaly detection) |
| AI | Claude API with tool use against `access` (optional, budget-capped) |
| Orchestration | Apache Airflow 3 (HTTP provider, LocalExecutor) + Postgres metadata DB |
| Frontend | React, TypeScript, Vite, Mantine (UI; `@mantine/charts` on Recharts for charts, lazy-loaded), `@tabler/icons-react` (icons, named imports), generated OpenAPI client |
| Quality tooling | ruff, mypy (strict), pytest, Testcontainers, import-linter; ESLint, Vitest |
| Observability | OpenTelemetry SDK and Collector, Prometheus, Loki, Tempo, Grafana; Oracle observability exporter |
| Containers | Docker (multi-arch amd64/arm64), Docker Compose, Caddy |
| CI/CD | GitHub Actions, GHCR, GitHub Pages |
| Hosting | GitHub Pages (frontend), OCI Always Free ARM VM (backend) |

## Mapping to the target role

| Role requirement | Where it is used |
|---|---|
| Oracle, SQL, PL/SQL, data modelling | `persistence` schema and packages; schema per service |
| Bitemporal historization | `CORE` observation model and as-of packages |
| ETL pipelines, market data integration | `ingestion` adapters and normalization |
| Data marts, data quality frameworks | `processing` marts and rule engine; validation gates; write–audit–publish |
| Python application and backend services | All backend services |
| REST APIs, downstream interfaces | `access` open host service; internal service interfaces |
| Apache Airflow | `orchestration` DAGs |
| CI/CD, Git, Docker, Linux, cloud/containers | GitHub Actions, multi-arch images, OCI VM |
| Operational readiness, end-to-end ownership | Per-service transparency, OpenTelemetry, Grafana dashboards and alerts as code |
| Historical recalculation, performance | `recalculation` DAG, bulk Arrow interfaces, partitioning |
| C++, QuantLib, Python/C++ integration | `processing` curve maths and native kernel |
| ML, AI, automation | Anomaly detection; grounded Q&A |
| Software architecture, clean code | DDD contexts, contracts, hexagonal services, [[principles/README|development principles]] |
