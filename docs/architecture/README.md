# Architecture

Overview: `ARCHITECTURE.md` at the repository root.

## Documents

1. [[01-context-map]]: bounded contexts, responsibilities, relationships, data ownership
2. [[02-interfaces-and-contracts]]: contracts package, REST standards, bulk interfaces, dependency rules
3. [[03-data-architecture]]: Oracle, schema per service, bitemporal model, PL/SQL standards
4. [[04-orchestration]]: Airflow role, DAGs, Airflow standards
5. [[05-tech-stack]]: technology per layer and mapping to the target role
6. [[06-repository-layout]]: monorepo tree and per-service structure
8. [[08-scalability]]: how the stack reaches 100× data volume
9. [[09-deployment]]: free live deployment and local environment
10. [[10-observability]]: per-service transparency, monitoring and logging strategy
11. [[11-service-design]]: facade vs. domain (DDD), `api`/`job` process types, service qualities
12. [[12-data-pipeline]]: stages, source contracts, revisions, source access policy, validation gates, replay, reference data, concurrency, retention, backup
13. [[13-build-and-ci]]: devbox toolchain, Taskfile rules, tested scripts, thin local-first CI, pre-commit hooks

## Decisions

| ADR | Decision | Status |
|---|---|---|
| [[0001-oracle-plsql]] | Oracle Free 23ai with PL/SQL as the database | Built |
| [[0002-service-per-bounded-context]] | One service and one schema per bounded context | Built |
| [[0003-rest-and-airflow]] | REST interfaces plus Airflow orchestration, no message broker | Built |
| [[0004-contracts-only-shared-code]] | Interface models are the only shared code | Built |
| [[0005-react-spa-on-github-pages]] | React SPA on GitHub Pages instead of Dash | Built |
| [[0006-quantlib-and-cpp-kernel]] | QuantLib plus a C++ kernel via pybind11 for curve maths | Planned (no QuantLib or C++ code yet) |
| [[0007-oci-always-free-hosting]] | Backend on OCI Always Free | In progress ([#182](https://github.com/MaxBernstetter/yield-lens/issues/182)) |
| [[0008-transparency-per-service]] | Transparency is a per-service capability, not a domain | Built |
| [[0009-observability-stack]] | OpenTelemetry plus a self-hosted Grafana stack (Prometheus, Loki, Tempo) | Partly built (OTel, Prometheus, Grafana, Tempo configs; no Loki) |
| [[0010-api-and-job-process-types]] | Each service runs as an `api` process plus ephemeral `job` containers | Built |
| [[0011-validation-gates-and-wap]] | Severity-based validation gates and write–audit–publish for marts | Built |
| [[0012-backup-and-restore]] | Daily Data Pump exports to OCI Object Storage, tested restore | Planned ([#238](https://github.com/MaxBernstetter/yield-lens/issues/238)) |
| [[0013-openlineage]] | OpenLineage for run and dataset lineage; value lineage stays per service | Planned (no OpenLineage code yet) |
| [[0014-taskfile-and-local-first-ci]] | Taskfile as single task entry point; thin CI that only calls tasks | Built |
| [[0015-pre-commit-hooks]] | pre-commit framework for git hooks | Built |
| [[0016-ecb-aaa-curve-as-first-source]] | ECB euro area AAA spot curve as the first source | Built |
| [[0017-commit-safe-knowledge-time]] | Knowledge clock: one locked row makes knowledge times increase in commit order | Built |
| [[0018-mantine-ui-and-charts]] | Mantine 9 for the frontend UI and `@mantine/charts` (Recharts) for charts, replacing Plotly.js | Built |
| [[0019-quality-results-as-of-checked-knowledge-time]] | Quality reads pick the latest check run per day with `checked_as_of <=` the read time | Built |
| [[0020-derived-measures-computed-on-read]] | Spreads, curvature and inversion are computed on read in processing; nothing is stored | Built |
