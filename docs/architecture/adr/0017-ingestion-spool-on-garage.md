# ADR 0017: Spool fetched windows in Garage while persistence is unavailable

**Status:** Accepted · 2026-10-18

## Context
An ingestion job fetches a window from the source and records it through the persistence service. When persistence or its Oracle database is down, the write fails and the fetched data is dropped. A rerun then downloads it again, which breaks the "fetch once" rule of the [[12-data-pipeline#Source access policy|source access policy]].

The raw layer ([#20](https://github.com/MaxBernstetter/investment-copilot/issues/20)) does not help. It lives in Oracle and is down in the same outage. Ingestion runs as short-lived job containers ([[0010-api-and-job-process-types]]), so a container's local disk does not outlive the run. The buffer has to be a backing service of its own, outside Oracle.

## Options

| Option | For | Against |
|---|---|---|
| **Garage** (self-hosted, S3 API) | Open source (AGPL-3.0); one small Rust binary built for small self-hosted clusters, including a single node; S3 API, so any S3 client works | Another container to run; on the same VM as Oracle in the demo |
| MinIO | Widely known S3 server | Ruled out by the project owner |
| OCI Object Storage | Managed; survives the loss of the VM | Proprietary cloud service; credentials and a cloud account for local development and CI |
| Docker volume mounted into the job containers | No new service | State on the host's disk, tied to one host; breaks at scale with `KubernetesPodOperator` |

## Decision
- When a write fails because persistence is **unavailable**, the job stores the fetched window as one **Parquet** object in a **Garage** bucket. Unavailable means a transport error, `500`, `502`, `503` or `504`. Every run, and a drain-only command, records the waiting objects oldest first before it writes anything new.
- The happy path is unchanged: windows are written to persistence directly, and only a failure writes to the spool.
- **Layout:** `<source>/pending/<fetched_at>_<window start>_<window end>.parquet`, so keys sort in fetch order. Objects refused by persistence (a `4xx`) move to `<source>/rejected/` and are kept.
- **Content:**
  - One row per observation. `value` is stored as text, so the published digits come back exactly.
  - The delivery and its run (source, run id, window, `Last-Modified`, fetch time, `spool_format`) are Parquet key-value metadata, so an empty window keeps them too.
- **Client:** [`obstore`](https://developmentseed.org/obstore/), the Python binding of the Rust `object_store` crate that Polars also uses. It ships in-memory and local-directory stores, so unit tests need no object-store server. Only plain `PUT`, `GET`, `LIST`, `DELETE` and copy are used, no conditional writes, so any S3-compatible store works.
- **Configuration:** `INGESTION_SPOOL__URL` (`s3://<bucket>`), `__ENDPOINT`, `__REGION`, `__ACCESS_KEY_ID` and `__SECRET_ACCESS_KEY`. The key is limited to the spool bucket.

## Consequences
- Twelve-factor VI ("all state lives in Oracle") gets one exception: the spool bucket. Like Oracle, it is an attached backing service (factor IV), addressed by configuration.
- Resending a window must be harmless. This relies on versioning ([#15](https://github.com/MaxBernstetter/investment-copilot/issues/15)): an unchanged value is a no-op, so a window that was partly recorded before the outage can be sent again.
- Order matters. A stale spooled value must never be recorded after a newer one for the same observation, or it would come back as a newer version. While the spool cannot be drained, new windows are spooled behind it.
- Knowledge time is when persistence finally stores a value, not the fetch time. The fetch time stays in the spool metadata and the run output.
- Garage runs on the same VM as Oracle in the demo. The spool covers an outage of persistence or the database, not the loss of the VM; that is the job of [[0012-backup-and-restore]].
- Garage is one more service to run and observe: a Compose service, a one-off setup task for the layout, bucket and key, and a health check.
