# Raw Deliveries

Ingestion keeps every answer a source gives, byte for byte, in its own `ING` schema: the raw (bronze) stage of [[12-data-pipeline]]. Every stored value can be traced back to the delivery it was parsed from, and replay reads the stored payloads instead of calling the source again.

Tracked in [#20](https://github.com/MaxBernstetter/yield-lens/issues/20). Code: `src/services/ingestion/db/`.

## Ownership

- `ING` belongs to ingestion alone (one schema per service, [[0002-service-per-bounded-context]]). Persistence never reads it; ingestion never touches `CORE`.
- Users, as in `CORE`: the schema owner `ING` (migrations only) and the runtime user `ING_APP`, which may only execute `ing_delivery` (no table access).
- A stored value names its delivery through `observation.delivery_id` in `CORE` ([[01-bitemporal-model]]): an opaque reference, no foreign key across schemas.
- Both schemas live in the same Oracle instance. A persistence-api outage leaves delivery writes working; an Oracle outage stops both.

## Table `delivery`

One row per answered source request. Insert-only: a delivery is never updated or deleted (it is the replay source, see [[12-data-pipeline#Lifecycle and retention]]).

| Column | Type | Null | Meaning |
|---|---|---|---|
| `delivery_id` | `NUMBER` identity | no | Primary key; sent to persistence as `delivery_id` |
| `source_id` | `VARCHAR2(64)` | no | Source, e.g. `ecb` |
| `run_id` | `VARCHAR2(128)` | no | Run that sent the request |
| `request_url` | `VARCHAR2(4000)` | no | Full request URL with its query string |
| `response_status` | `NUMBER(3)` | no | HTTP status, e.g. `200`, `304`, or the source's `404` "no data" |
| `fetched_at` | `TIMESTAMP(6)` | no | When ingestion received the answer (UTC); partition key |
| `last_modified` | `TIMESTAMP(6)` | yes | `Last-Modified` of the answer (UTC): publication time, never a knowledge time |
| `etag` | `VARCHAR2(512)` | yes | `ETag` of the answer, if any |
| `payload` | `BLOB` (SecureFile) | yes | Response body byte for byte; `NULL` for an empty delivery |
| `payload_sha256` | `VARCHAR2(64)` | yes | SHA-256 of the payload in lowercase hex, computed by ingestion; given exactly when a payload is |

- **Empty deliveries** (the source's "no data" answer, `304`, an empty `200` body) are rows without payload and hash.
- Partitioned by month of `fetched_at` (interval partitioning), so old partitions can be compressed or moved without touching recent ones.
- Volume: about 260 KB of CSV per year of ECB grid data, about 6 MB for the full history.

## Package `ing_delivery`

- `record_delivery(source_id, run_id, request_url, response_status, fetched_at, last_modified, etag, payload, payload_sha256) return delivery_id`: stores one answer. Every call is a new delivery, also for the same request. The caller owns the transaction.
- `get_deliveries(source_id, fetched_from, fetched_to) return sys_refcursor`: the deliveries of a source fetched in `[fetched_from, fetched_to)` (UTC), payload included, ordered by `fetched_at`, then `delivery_id`.

## Writing deliveries

The ECB load ([[03-ecb-load]]) stores every answer through `OracleDeliveryStore` (`infrastructure/ing/`) before it parses it, and commits it on its own: an answer that fails validation is kept. Every value recorded from it carries its `delivery_id`. The hash is SHA-256 over the stored bytes; the payload is bound as a LOB, so its size is not limited by PL/SQL `RAW`. The connection settings are `INGESTION_DB__*` ([[03-ecb-load#Configuration]]).

## Replay

`ingestion-load-ecb replay --fetched-from D1 --fetched-to D2` (task `ingestion:load:ecb:replay FROM=… TO=…`) reads the ECB deliveries fetched on those days (UTC) from `ING`, parses each payload again with the current mapping and records its values through persistence, each naming its `delivery_id`. It creates no source client, so it can never call the ECB.

- Deliveries are streamed one at a time (memory bounded by one payload) and replayed in fetch order, so a later answer wins, as in the original loads.
- A payload whose SHA-256 no longer matches the stored hash fails the run (`CorruptDeliveryError`) before any of its values is sent; an invalid payload fails it with `InvalidPayloadError`.
- Persistence treats unchanged values as no-ops; values that differ become new versions. A changed normalization version alone is not version-relevant ([[01-bitemporal-model]]).
- **Limits today:** values are sent with `change_reason = initial` (a `replay` reason is a proposed follow-up); a period that ends before the latest delivery of a date reopens an older value as the current version, so replay up to the latest fetch day. The `replay` DAG ([[12-data-pipeline#Reproducibility and replay]]) will call this command.

## Migrations and tests

- Liquibase, as in persistence: `db/admin/` (users, run as `SYSTEM`; passwords from `ING_PASSWORD`, `ING_APP_PASSWORD`) and `db/ing/` (table, package, grants, run as `ING`).
- Locally: `task persistence:db:start`, then `task ingestion:db:migrate` (the same database, at `INGESTION_DB__DSN`).
- `task ingestion:test:integration`: Testcontainers Oracle Free with both changelogs applied; migration tests and the utPLSQL suite `ut_ing_delivery` (payload byte for byte with metadata, empty delivery, one row per call, hash required with a payload and well-formed, reads by source and fetch period in fetch order). `tests/integration/test_delivery_store.py` reads deliveries back through the adapter and rejects a tampered payload; `tests/unit/test_load_ecb_job.py` proves that replay records the stored values with their delivery ids and never calls the source.
