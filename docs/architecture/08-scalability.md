# Scalability

Target: handle **100× the demo data volume** (≈100 GB including history) without redesign. The free demo is deliberately small; scaling means changing infrastructure, not architecture.

## Levers

| Area | Demo | At 100× |
|---|---|---|
| Oracle storage | Plain tables + indexes | Interval partitioning by `valid_date`; local indexes on knowledge-time columns; partition pruning for as-of queries |
| Oracle compute | Oracle Free (2 CPU threads, 12 GB user data) | Autonomous Database or licensed Oracle; parallel and partition-wise queries |
| Writes | Array DML via packages | Same packages; bulk `FORALL`, direct-path loads for backfills |
| Service-to-service bulk | Arrow streams | Same, parallelized by date chunk |
| Marts | Write–audit–publish per load | Same pattern, applied only to affected partitions (partition exchange) |
| Backup | Daily Data Pump export | RMAN with archived logs or managed backups (point-in-time recovery) |
| Recalculation | Single task per range | Airflow task mapping over chunks; C++ kernel for hot loops |
| Services (`api`) | One small container each | Stateless replicas behind the proxy; scale to zero on a serverless or KEDA platform |
| Batch (`job`) | Ephemeral containers via `DockerOperator`, 0 when idle | Pods via `KubernetesPodOperator`; parallelism bounded by Airflow pools |
| Orchestration | LocalExecutor | CeleryExecutor / KubernetesExecutor; pools protect Oracle |
| Read traffic | ETag caching | CDN / reverse-proxy cache; past `as_of` responses are immutable |
| Observability | Single-node Prometheus, Loki, Tempo | Object storage backends, trace sampling, or a managed backend; only the collector config changes |

## Design properties that make this possible

- **Insert-only history:** no update hotspots, and it partitions cleanly by time.
- **Chunkable interfaces:** every bulk interface is keyed by date range, so work parallelizes naturally.
- **Stateless services:** state lives in Oracle; services can be replicated.
- **Thin orchestration:** scaling Airflow doesn't touch business code.

## Verification

A synthetic load generator (scenario mechanism at volume) is used to show 100× behaviour on larger infrastructure: as-of query latency, recalculation throughput, mart refresh time.
