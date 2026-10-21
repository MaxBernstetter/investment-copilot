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
  - Ports on localhost: 1521 (Oracle), 8001 (persistence api), 8002 (processing api), 8003 (ingestion api), 8000 (access api, read-only; the frontend calls it), 3300 (Grafana), 9090 (Prometheus), 3200 (Tempo) (observability profile).
  - The stack uses the same ports as `persistence:db:start`. Stop that stack first (`persistence:db:stop`).
  - **Airflow (opt-in):** `task dev:airflow:up` starts the `airflow` Compose profile on top of the same project: a Postgres metadata database, one-shot init (`db migrate`, admin user `airflow`/`airflow`, pool import from `src/orchestration/pools.json`), scheduler, DAG processor and API server (UI at `http://127.0.0.1:8088`; host port 8088 avoids clashes with other tools that bind `0.0.0.0:8080`, e.g. Hasura). It builds and tags the ingestion and processing job images as `yieldlens-ingestion:local` and `yieldlens-processing:local`, which the DAGs run via `DockerOperator`. Only `airflow-scheduler` mounts the Docker socket. With LocalExecutor it is the one process that starts job containers (see [[0010-api-and-job-process-types]]). It joins the host's `docker` group, whose GID `task dev:airflow:up` detects as `DOCKER_GID`. Membership in that group is root-equivalent on the host, and ADR 0010 requires securing it. In the local demo the socket is limited to the scheduler, the profile is opt-in, and the UI is bound to 127.0.0.1. At scale, jobs run as Kubernetes pods (ADR 0010) and need no socket; the live VM stack ([#182](https://github.com/MaxBernstetter/yield-lens/issues/182)) inherits this scheduler-only mount. A plain `docker compose --profile airflow up` without the Taskfile leaves DOCKER_GID=0 and tasks fail with PermissionError; on Docker Desktop GID 0 is correct. `task dev:airflow:down` stops only the Airflow profile; `task dev:up` / `dev:down` / `dev:reset` are unchanged. Validate wiring with `task dev:compose:config`.
  - **Observability (opt-in):** `task dev:obs:up` starts the `observability` Compose profile on top of `dev:up`, and restarts the persistence, processing, access and ingestion apis with `OTEL_*` settings. `task dev:obs:down` stops the profile (keeps its data) and restarts the apis without `OTEL_*`. `task dev:obs:smoke` checks the wiring, the Grafana datasources, OTLP metrics and a trace (telemetrygen) and needs the profile up. The profile has four services: an OpenTelemetry Collector (internal only, OTLP on 4317/4318), Prometheus, Tempo and Grafana. Grafana is at `http://127.0.0.1:3300` (port 3000 is often taken by other local Grafana stacks), user `admin`, password `GRAFANA_ADMIN_PASSWORD` (the Taskfile sets a local default). Prometheus (9090) and Tempo (3200) are bound to 127.0.0.1 as well. `compose.observability.yaml` adds the `OTEL_*` settings to the apis and the `ingestion` and `processing-job` services; the Taskfile sets `COMPOSE_FILE` to include it only while the collector runs, so plain `dev:up` stays unchanged. Jobs export delta metrics and the collector converts them to cumulative (`deltatocumulative`) and drops `service.instance.id` so short-lived jobs do not create one series per run. Retention is 15 d for metrics and 3 d for traces. Logs and notifications are not set up yet. It also sets `YIELDLENS_JOB_OTEL_ENDPOINT` on `airflow-scheduler`; when it is non-empty, the scheduler passes `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` (`ingestion-job`, `processing-job`) and delta temporality to the job containers it starts on `yieldlens-dev_default`. `task dev:obs:up` and `dev:obs:down` recreate the scheduler when it runs, so the setting follows the profile. Measured idle RAM of the four services: about 570 MB in total (`docker stats`, 2 minutes after the corrected-yield scenario: collector 89 MiB, Prometheus 56 MiB, Tempo 79 MiB, Grafana 316 MiB). Grafana provisions the services' dashboards and alert rules ([[10-observability]]). `task dev:obs:firing-check` proves that `quality-warn` fires and clears (manual, not CI).
- **Live:** the Compose stack on the VM with `compose.vm.yaml` (see [Live VM](#live-vm)), plus the frontend on Pages.

## Delivery

GitHub Actions publishes multi-arch service images as `ghcr.io/maxbernstetter/yield-lens-<service>:<commit sha>` (`linux/amd64` and `linux/arm64`) via `images.yml` on every push to `main`, after a Trivy scan. It also deploys the frontend to Pages and updates the VM over SSH (`docker compose pull && up -d`, migrations, readiness check). See [[07-delivery-and-security]].

## Frontend on GitHub Pages

- **Workflow:** `.github/workflows/pages.yml` runs on pushes to `main` that change the frontend, and on manual dispatch. Job `configured` reads `vars.VITE_ACCESS_URL` from the `github-pages` Environment; the variable is read in its own job because environment variables are not visible in a job-level `if` of the job that uses the environment. Jobs `build` (`task frontend:build:pages`, then the Pages artifact) and `deploy` (`actions/deploy-pages`) run only when it is set. Until then the run is skipped, not red. Set the variable to the VM domain without a trailing slash, e.g. `https://<subdomain>.duckdns.org`.
- **Pages source:** a one-off repository setting, Settings → Pages → Source "GitHub Actions".
- **Build:** `vite build --mode pages` sets the base to `/yield-lens/`. The Vite config refuses a Pages build without `VITE_ACCESS_URL`, and the task checks that the bundle references `/yield-lens/assets/`.
- **CORS:** the VM allows only the Pages origin `https://maxbernstetter.github.io` (`ACCESS_CORS_ORIGINS`, set in the VM overlay, #182).
- **Offline state:** when the VM is unreachable, the app shows "Backend offline" with a "Try again" button (see [[01-frontend]]). The page itself stays available.

## Backup

Daily Data Pump exports of all schemas go to OCI Object Storage (Always Free), with a tested restore procedure. See [[0012-backup-and-restore]].

## Constraints and caveats

- OCI sign-up requires card verification. Always Free resources are not charged.
- Ampere A1 capacity is sometimes unavailable in a region; retry or choose another region.
- Oracle Free limits: 2 CPU threads, 2 GB RAM, 12 GB user data. Enough for the demo dataset.
- Claude-based Q&A has per-request cost. It is disabled or hard budget-capped in the public demo.
- If the VM is unavailable, the frontend shows a clear "backend offline" state.

See [[0007-oci-always-free-hosting]].
