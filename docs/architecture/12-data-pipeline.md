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
- **Politeness:** every source call follows the [[#Source access policy]].

## Source access policy

Public sources are shared infrastructure, and most publish no rate limit. A blocked or banned client stops the platform, so ingestion limits itself. The rules apply to every source; the values per source are in its source note (e.g. [[01-data-sources]]).

- **One client per source:** all calls to a source go through the source adapter's HTTP client. Nothing else (DAGs, scripts, tests) calls a source directly.
- **Rate limit:** per source, a maximum number of concurrent requests (default 1) and a minimum interval between requests. Both come from configuration.
- **Sequential chunks:** backfill chunks for one source run one after another. Airflow enforces this with a pool of size 1 per source, so task mapping never fans out against a source.
- **Bounded retries:**
  - Retry only on network errors, timeouts, `429` and `502`/`503`/`504`.
  - Exponential backoff with jitter; `Retry-After` is honoured.
  - At most 3 attempts per request inside the client and at most 2 Airflow task retries. One failing load therefore costs at most 9 requests.
  - Any other `4xx` fails fast. Source-specific "no data" answers (e.g. the ECB's `404` for an empty window) are mapped to an empty delivery and never retried.
- **Small requests:** request only the series, fields and date window that are needed, and batch series into one request where the source supports it.
- **Conditional requests:** send `If-Modified-Since` / `If-None-Match` where supported, and use incremental parameters (e.g. `updatedAfter`).
- **Fetch once:** raw payloads are stored, so replay and reprocessing read from raw and never download again.
- **Identification:** a `User-Agent` naming YieldLens, its version and the repository URL. No personal contact data.
- **Off-peak timing:** loads are scheduled after the source's publication time with an offset, not on the exact minute of publication.
- **No live calls in CI:** tests use recorded payloads. A live check against a source is a manual task only.
- **Kill switch:** each source can be disabled by configuration, without a deploy.
- **Terms of use:** each source note records its licence and attribution duty. The API and the UI carry the attribution.
- **Observable:** requests are counted per source and status (`yl_ingestion_source_requests_total{source,status}`), so throttling shows up on the dashboard before it becomes a ban.

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
