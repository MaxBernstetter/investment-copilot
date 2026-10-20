# Deployment

Goal: a **live, free** web app that shows the full functionality. It is not sized for production load (see [[08-scalability]]).

## Topology

```
Browser ──▶ GitHub Pages (React SPA)
   │
   └──HTTPS──▶ OCI Always Free ARM VM (4 OCPU, 24 GB)
               Caddy (TLS, rate limit) ──▶ access
               internal network: ingestion, persistence, processing (api),
                                 job containers (started on demand by Airflow),
                                 Airflow (+ Postgres), Oracle Free 23ai,
                                 OTel Collector, Prometheus, Loki, Tempo, Grafana
```

| Component | Where | Public |
|---|---|---|
| Frontend | GitHub Pages | Yes |
| `access` | VM behind Caddy (HTTPS, free domain e.g. DuckDNS, Let's Encrypt) | Yes, read-only |
| Other services, Oracle, Airflow | VM, internal Docker network | No; SSH tunnel for admin |
| Grafana | VM, internal Docker network | No by default; optional read-only public dashboard |

## Environments

- **Local:** the same Docker Compose stack as the VM (dev/prod parity), defined in `src/deploy/compose.yaml`. The frontend runs on the Vite dev server against local `access`.
  - `task dev:up` starts Oracle Free, applies the Liquibase migrations for `CORE`, `ING` and `PROC` and builds and starts the persistence, processing and access apis. It is idempotent and waits until the services are healthy. The local stack does not include the spool (Garage); ingestion's spool is run separately (`ingestion:spool:*`).
  - `task dev:seed` runs the ingestion job (`src/scripts/dev-seed.sh`) to load ECB history from `START` (default `2024-01-01`) in two steps, with a knowledge time between them, so time travel can be tried locally. It makes live ECB calls and is never run in CI.
  - `task dev:down` stops the stack and keeps its data; `task dev:reset` also removes the volumes.
  - Ports on localhost: 1521 (Oracle), 8001 (persistence api), 8002 (processing api), 8000 (access api, read-only; the frontend calls it).
  - The stack uses the same ports as `persistence:db:start`. Stop that stack first (`persistence:db:stop`).
- **Live:** the Compose stack on the VM, plus the frontend on Pages.

## Delivery

GitHub Actions builds multi-arch images to GHCR, deploys the frontend to Pages, and updates the VM over SSH (`docker compose pull && up -d`, migrations, readiness check). See [[07-delivery-and-security]].

## Backup

Daily Data Pump exports of all schemas go to OCI Object Storage (Always Free), with a tested restore procedure. See [[0012-backup-and-restore]].

## Constraints and caveats

- OCI sign-up requires card verification. Always Free resources are not charged.
- Ampere A1 capacity is sometimes unavailable in a region; retry or choose another region.
- Oracle Free limits: 2 CPU threads, 2 GB RAM, 12 GB user data. Enough for the demo dataset.
- Claude-based Q&A has per-request cost. It is disabled or hard budget-capped in the public demo.
- If the VM is unavailable, the frontend shows a clear "backend offline" state.

See [[0007-oci-always-free-hosting]].
