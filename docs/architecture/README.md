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

| ADR | Decision |
|---|---|
| [[0001-oracle-plsql]] | Oracle Free 23ai with PL/SQL as the database |
| [[0002-service-per-bounded-context]] | One service and one schema per bounded context |
| [[0003-rest-and-airflow]] | REST interfaces plus Airflow orchestration, no message broker |
| [[0004-contracts-only-shared-code]] | Interface models are the only shared code |
| [[0005-react-spa-on-github-pages]] | React SPA on GitHub Pages instead of Dash |
| [[0006-quantlib-and-cpp-kernel]] | QuantLib plus a C++ kernel via pybind11 for curve maths |
| [[0007-oci-always-free-hosting]] | Backend on OCI Always Free |
| [[0008-transparency-per-service]] | Transparency is a per-service capability, not a domain |
| [[0009-observability-stack]] | OpenTelemetry plus a self-hosted Grafana stack (Prometheus, Loki, Tempo) |
| [[0010-api-and-job-process-types]] | Each service runs as an `api` process plus ephemeral `job` containers |
| [[0011-validation-gates-and-wap]] | Severity-based validation gates and write–audit–publish for marts |
| [[0012-backup-and-restore]] | Daily Data Pump exports to OCI Object Storage, tested restore |
| [[0013-openlineage]] | OpenLineage for run and dataset lineage; value lineage stays per service |
| [[0014-taskfile-and-local-first-ci]] | Taskfile as single task entry point; thin CI that only calls tasks |
| [[0015-pre-commit-hooks]] | pre-commit framework for git hooks |
| [[0016-ecb-aaa-curve-as-first-source]] | ECB euro area AAA spot curve as the first source |
