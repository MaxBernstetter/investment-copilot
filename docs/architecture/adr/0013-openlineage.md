# ADR 0013: OpenLineage for run and dataset lineage

**Status:** Accepted · 2026-10-18

## Context
Lineage exists at two levels:
- **Value level:** which source, run and version produced this yield. This is domain data, owned per service ([[0008-transparency-per-service]]).
- **Dataset/job level:** which job read and wrote which dataset in which run.

For the second level an open standard exists, OpenLineage. Airflow supports it natively.

## Decision
- Emit **OpenLineage** events for runs and datasets: from Airflow (built-in provider) and from `job` processes (OpenLineage Python client).
- Value-level lineage stays in the services' transparency interface. OpenLineage run ids are stored with each service run to link both levels.
- A lineage backend (e.g. Marquez) is **optional**. Events can go to the OpenTelemetry Collector/log stream until a backend is needed.

## Consequences
- Standard, tool-agnostic job lineage at low cost.
- No extra service required for the demo.
- Two lineage levels must be kept linked via run ids.
