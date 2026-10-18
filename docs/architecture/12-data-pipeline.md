# Data Pipeline

How data moves from sources to consumers, and the rules that keep it correct, reproducible and safe to rerun. Service anatomy is in [[11-service-design]]; scheduling is in [[04-orchestration]].

## Stages

The pipeline follows the layered (bronze/silver/gold) pattern, mapped onto service ownership:

| Stage | Layer | Owner / schema | Content |
|---|---|---|---|
| Raw | Bronze | ingestion / `ING` | Source payloads exactly as delivered, immutable, with delivery metadata |
| Core | Silver | persistence / `CORE` | Normalized, validated, bitemporal observations (published and derived) |
| Marts | Gold | processing / `PROC` | Consumer-ready marts, published only after passing validation gates |

## Source contracts and schema drift

- Every source has a **declared payload schema** (versioned, in ingestion) plus expectations: publication time, update frequency, value units.
- Each delivery is compared against the declared schema and against the previously observed schema:
  - **Compatible change** (e.g. new optional field): accepted, logged, warning alert.
  - **Breaking change** (missing field, type change): the delivery is quarantined and a blocking alert is raised. Nothing reaches core.
- Shape and type validation at the ingestion boundary uses **Pandera** on Polars frames. Domain rules stay in processing.

## Extraction and revisions

- **Incremental by default:** fetch by date window. Use conditional requests (ETag / Last-Modified) where the source supports them.
- **Revision lookback:** sources revise past values silently. Each daily load re-fetches a configurable **lookback window** (e.g. the last N business days) per source. Unchanged values are no-ops. Changed values become new versions with reason `revision`.
- **Politeness:** respect source rate limits; back off on `429`/`503`; follow the source's terms of use.

## Validation gates

Quality rules (processing) have a severity:

| Severity | Effect |
|---|---|
| `block` | Affected slice (curve × date range) is quarantined. It is not published to marts or `access`, and an alert is raised. |
| `warn` | Data is published and flagged in response metadata (`quality: warning`); alert raised. |
| `info` | Recorded only. |

Gates run after each stage transition: raw → core (schema, completeness) and core → marts (plausibility, curve sanity, cross-source). See [[0011-validation-gates-and-wap]].

## Write–audit–publish (marts)

1. **Write:** build the new mart content into a staging table.
2. **Audit:** run blocking validation on the staging content.
3. **Publish:** atomically swap it into the mart via **Oracle partition exchange**. Readers never see a half-built mart.
4. If the audit fails, the current mart stays as is and an alert is raised.

## Reproducibility and replay

- Everything that shapes data is versioned:
  - the source schema version
  - the **normalization version** (mapping rules in ingestion)
  - the method version (processing)
  - the code version (image SHA)
- Every run records all four, plus the reference-data version used.
- **Replay:** the `replay` DAG rebuilds core observations for a date range from raw payloads with a given normalization version. The results enter as new versions (reason `replay`), so history is preserved and the replay itself is auditable.

## Reference data

Business calendars, maturity/tenor conventions, day-count conventions and curve definitions are owned, versioned datasets:

| Reference data | Owner |
|---|---|
| Source registry, source calendars (publication days) | ingestion |
| Curve definitions, maturity grid | persistence |
| Market calendars, day-count and interpolation conventions | processing (calendars sourced from QuantLib) |

Completeness checks use market calendars, so a holiday is not reported as a missing day.

## Concurrency control

- **Writes:** persistence takes a lock per curve and valid-date range inside the PL/SQL write package (`DBMS_LOCK`/row locks), so overlapping writers serialize instead of racing.
- **DAGs:** `max_active_runs = 1` per DAG and data interval, plus a mutex (an Airflow pool of size 1) per curve-and-range for backfill, replay and recalculation.
- **Jobs:** a job checks for a conflicting active run before starting and fails fast with a clear reason.

## Lifecycle and retention

| Data | Retention |
|---|---|
| Raw payloads | Kept (they are the replay source); old partitions compressed |
| Core versions | Kept forever (audit trail); old partitions compressed |
| Marts | Current plus rebuildable; no history needed beyond core |
| Quarantine | Until resolved, then kept with resolution note |
| Idempotency keys | 30 days |
| Telemetry | See [[10-observability]] |

## Backup and restore

Daily Oracle Data Pump export per schema to OCI Object Storage, with retention and a documented, regularly tested restore procedure. See [[0012-backup-and-restore]].
