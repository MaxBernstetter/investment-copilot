# Service Design

Every service meets the same six qualities: **robust, idempotent, transparent, performant, elastic, and DDD-structured** with a clear public facade. This note defines what each one means and which mechanisms deliver it. Coding rules are in `docs/development/principles/`.

## Anatomy of a service

```
            other services / Airflow / access
                         │
 ┌───────────────────────▼────────────────────────┐
 │ FACADE (published language)                    │
 │  REST adapter · job entrypoint · contract ↔    │
 │  domain mapping · validation · idempotency     │
 ├────────────────────────────────────────────────┤
 │ APPLICATION  use cases · transactions · ports  │
 ├────────────────────────────────────────────────┤
 │ DOMAIN  aggregates · value objects · rules     │  ← no I/O, no contracts
 ├────────────────────────────────────────────────┤
 │ INFRASTRUCTURE  Oracle repositories (PL/SQL) · │
 │  clients to other services (anti-corruption)   │
 └────────────────────────────────────────────────┘
```

Rules:
- **The facade is the only thing other services see:** the REST interface plus the job entrypoint, both defined by `contracts/`. It is thin: it validates, maps contract ↔ domain, enforces idempotency, and calls a use case. It holds no business rules.
- **The domain owns the rules:**
  - Aggregates (e.g. `Observation` with its versions) enforce their invariants.
  - The domain never imports contract models, frameworks or database code.
- **The application layer orchestrates:**
  - One use case = one transaction boundary.
  - It depends only on ports (interfaces), which infrastructure implements.
- **Infrastructure translates outward:**
  - Clients to other services act as an **anti-corruption layer**, mapping the other service's contract into this service's own model.
  - PL/SQL packages are internal to the service, never a facade for others.

Directory mapping: see [[06-repository-layout]].

## Process types: `api` and `job`

Each service runs from one image in two process types (twelve-factor VIII, see [[0010-api-and-job-process-types]]):

| Type | Purpose | Lifecycle |
|---|---|---|
| `api` | Interactive requests: queries, small commands, transparency interface | Long-running, small, horizontally scalable; scales to zero where the platform allows |
| `job` | Heavy batch work: loads, backfill chunks, recalculation, mart rebuilds | Ephemeral: started per chunk by Airflow, exits when done; 0 instances when idle |

Both types call the same application layer; only the facade differs.

## Qualities

### Robust
- **Timeouts** on every outbound call and DB statement; no unbounded waits.
- **Retries:** only for idempotent operations, with exponential backoff and jitter; capped attempts.
- **Circuit breaker** on outbound service clients; fail fast when a dependency is down.
- **Bulkheads:** separate connection pools for `api` and `job` paths, so batch load can't starve queries.
- **Graceful degradation:** `access` serves cached responses (marked stale) when an upstream service is unavailable.
- **Bad data is quarantined, not fatal:** invalid records are rejected with a reason and alerted; the rest of the batch continues.
- **Lifecycle:**
  - Readiness depends on the database and required config.
  - Graceful shutdown on `SIGTERM` finishes or abandons in-flight work safely.

### Idempotent
- Every operation assumes **at-least-once** execution.
- **Commands:** `POST` requires an `Idempotency-Key`. The key and the result are stored in the service's schema, and a repeat returns the stored result.
- **Jobs:** the run id is deterministic, derived from DAG, data interval and chunk. A rerun of the same chunk replaces or confirms its own output and never duplicates it.
- **Writes are natural-key based:** recording an unchanged value is a no-op. Only a changed value creates a new version (bitemporal insert-only).

### Transparent
- Business data, alerts and system data per [[10-observability]].
- Every run, including job runs, appears in the service's transparency interface with its outcome and record counts.

### Performant
- **Targets (demo):** p95 < 300 ms for single-curve as-of queries at `access`; a daily load completes in minutes.
- **Data work:** set-based SQL and bulk PL/SQL; Arrow for bulk transfer; vectorized or C++ code for numerical hot paths.
- **Calls:** batch endpoints instead of N+1 calls across services; async I/O in the `api` process.
- **Connections:** connection pooling (python-oracledb pools; DRCP for many short-lived job processes).
- **Caching:** past as-of responses are immutable and cached at `access` and the proxy.
- **Regression checks:** benchmark tests with thresholds run in CI for critical paths.

### Elastic: cheap when idle, handles spikes
- **Idle:** no batch capacity is running. Jobs scale to 0, and `api` processes are small and stateless, able to scale to zero where the platform allows.
- **Spikes:**
  - Batch: more job instances via Airflow task mapping; Airflow pools protect Oracle (backpressure).
  - Read: more `api` replicas plus HTTP caching. Rate limiting at the edge protects the platform.
- **Fast startup:** a few seconds, with no warm-up state, so new instances are useful immediately.
- **Fixed cost:** Oracle doesn't scale to zero. It is the fixed baseline, protected by pools and limits.
