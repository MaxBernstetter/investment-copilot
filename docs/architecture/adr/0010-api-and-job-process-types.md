# ADR 0010: `api` and `job` process types per service

**Status:** Accepted · 2026-10-18 · Amends [[0003-rest-and-airflow]]

## Context
Services must be cheap when idle and able to handle workload spikes. Batch work (loads, backfills, recalculation, mart rebuilds) is bursty and heavy. Interactive queries are light and continuous. Running both in one long-lived process means paying for peak capacity all the time, and lets batch load starve queries.

## Decision
Each service image provides two process types:
- **`api`:** long-running REST facade for queries, small commands and the transparency interface.
- **`job`:** ephemeral batch entrypoint with a versioned, contract-defined parameter set (e.g. operation, data interval, chunk). It is started by Airflow per chunk and exits when done.

Airflow starts jobs as containers:
- Demo: `DockerOperator`.
- At scale: `KubernetesPodOperator`, with no DAG redesign.

Commands that need no heavy work still go through REST.

## Consequences
- Zero batch capacity when idle; spikes are handled by running more job containers in parallel, bounded by Airflow pools.
- Batch and interactive load are isolated (separate processes and connection pools).
- Two facades per service (REST and job), both defined in `contracts/` and both calling the same application layer.
- Airflow needs access to the container runtime (Docker socket in the demo), which must be secured.
- Oracle remains a fixed-cost baseline; DRCP is used for many short-lived connections.
