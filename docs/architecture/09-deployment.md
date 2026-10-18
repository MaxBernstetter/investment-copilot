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

- **Local:** the same Docker Compose stack as the VM (dev/prod parity). The frontend runs on the Vite dev server against local `access`.
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
