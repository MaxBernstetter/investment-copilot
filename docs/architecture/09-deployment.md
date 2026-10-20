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
  - `task dev:up` starts Oracle Free, applies the Liquibase migrations for `CORE`, `ING` and `PROC` and builds and starts the persistence, processing, access and ingestion apis. It is idempotent and waits until the services are healthy. The local stack does not include the spool (Garage); ingestion's spool is run separately (`ingestion:spool:*`).
  - `task dev:seed` runs the ingestion job (`src/scripts/dev-seed.sh`) to load ECB history from `START` (default `2024-01-01`) in two steps, with a knowledge time between them, so time travel can be tried locally. It makes live ECB calls and is never run in CI.
  - `task dev:down` stops the stack and keeps its data; `task dev:reset` also removes the volumes.
  - Ports on localhost: 1521 (Oracle), 8001 (persistence api), 8002 (processing api), 8003 (ingestion api), 8000 (access api, read-only; the frontend calls it).
  - The stack uses the same ports as `persistence:db:start`. Stop that stack first (`persistence:db:stop`).
  - **Airflow (opt-in):** `task dev:airflow:up` starts the `airflow` Compose profile on top of the same project: a Postgres metadata database, one-shot init (`db migrate`, admin user `airflow`/`airflow`, pool import from `src/orchestration/pools.json`), scheduler, DAG processor and API server (UI at `http://127.0.0.1:8088`; host port 8088 avoids clashes with other tools that bind `0.0.0.0:8080`, e.g. Hasura). It builds and tags the ingestion and processing job images as `yieldlens-ingestion:local` and `yieldlens-processing:local` for a follow-up that runs tasks via `DockerOperator`. Airflow reaches the Docker socket through the host's `docker` group: `task dev:airflow:up` detects its GID (`DOCKER_GID`) and the Airflow services join it, which grants the same root-equivalent access ADR 0010 already accepts for the demo. `task dev:airflow:down` stops only the Airflow profile; `task dev:up` / `dev:down` / `dev:reset` are unchanged. Validate wiring with `task dev:compose:config`.
- **Live:** the Compose stack on the VM, plus the frontend on Pages.

## Delivery

GitHub Actions publishes multi-arch service images as `ghcr.io/maxbernstetter/yield-lens-<service>:<commit sha>` (`linux/amd64` and `linux/arm64`) via `images.yml` on every push to `main`, after a Trivy scan. It also deploys the frontend to Pages and updates the VM over SSH (`docker compose pull && up -d`, migrations, readiness check). See [[07-delivery-and-security]].

## Backup

Daily Data Pump exports of all schemas go to OCI Object Storage (Always Free), with a tested restore procedure. See [[0012-backup-and-restore]].

## Constraints and caveats

- OCI sign-up requires card verification. Always Free resources are not charged.
- Ampere A1 capacity is sometimes unavailable in a region; retry or choose another region.
- Oracle Free limits: 2 CPU threads, 2 GB RAM, 12 GB user data. Enough for the demo dataset.
- Claude-based Q&A has per-request cost. It is disabled or hard budget-capped in the public demo.
- If the VM is unavailable, the frontend shows a clear "backend offline" state.

See [[0007-oci-always-free-hosting]].
