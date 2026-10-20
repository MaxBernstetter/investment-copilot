# Observability and Transparency

Transparency is not a separate domain. **Every service is responsible for its own transparency** (see [[0008-transparency-per-service]]). The platform provides one monitoring setup, and each service applies an instance of it (see [[0009-observability-stack]]).

## Three kinds of transparency data

| Kind | What | Owned by | Stored in | Shown in |
|---|---|---|---|---|
| **Business data** | Runs, lineage, quality results, diffs, impact | The service whose logic produced it | The service's own schema | Frontend, via the transparency interface |
| **Alerts** | Something went wrong: business (source late, quality failed) or system (service down, error rate) | Business alerts: the service. System alerts: the platform | Business: the service's schema. System: Prometheus | Business: frontend and notifications. System: Grafana and notifications |
| **System data** | Metrics, logs, traces | Emitted by every service, platform components and Oracle | Prometheus, Loki, Tempo | Grafana |

## Transparency interface (every service)

Every domain service implements the same contract (`contracts.transparency.v1`, `src/contracts/src/contracts/transparency/v1/`), next to its own domain interface:

| Endpoint | Content |
|---|---|
| `GET /v1/runs`, `GET /v1/runs/{run_id}` | Runs of this service: status, interval, duration, record counts, errors |
| `GET /v1/lineage/{ref}` | Lineage of a value or artifact *within this service*, with links to upstream refs in other services |
| `GET /v1/alerts` | Currently active and recent business alerts of this service |

- Cross-service lineage is assembled by following the upstream refs (done by `access` for the frontend).
- No central transparency store exists.

## Data observability (five pillars)

Each service covers the pillars for the data it owns:

| Pillar | Signal | Owner |
|---|---|---|
| Freshness | Time since last successful load vs. **freshness SLO per source** (e.g. available ≤ 2 h after source publication) | ingestion |
| Volume | Records per delivery vs. **expected range** per source (alert on drop or spike) | ingestion |
| Schema | Delivery vs. declared source schema (drift alert, quarantine on breaking change) | ingestion |
| Distribution | Plausibility, curve sanity and anomaly checks | processing |
| Lineage | Value lineage (transparency interface) plus run/dataset lineage (OpenLineage, [[0013-openlineage]]) | all |

Platform data-safety signal: backup age and success ([[0012-backup-and-restore]]).

## Monitoring setup (platform)

```
service ──OTLP──▶ OpenTelemetry Collector ──▶ Prometheus (metrics) ─┐
   │ stdout JSON logs ──▶ Collector ─────────▶ Loki (logs) ──────────┼──▶ Grafana (dashboards, alerting)
   └ traces ──OTLP──▶ Collector ─────────────▶ Tempo (traces) ───────┘
Oracle exporter, Airflow (OTel metrics), Caddy, node/container exporters ──▶ Prometheus
```

- **Instrumentation standard:** OpenTelemetry SDK in every service (FastAPI, HTTP client and oracledb auto-instrumentation, plus domain metrics). It is configured only via `OTEL_*` environment variables. There is no shared library: OpenTelemetry is the shared standard.
- **Backends:** Prometheus, Loki, Tempo and Grafana, self-hosted in the Compose stack.
  - Collectors and exporters are swappable: moving to a managed backend (e.g. Grafana Cloud) only changes the collector exporter config.

## What each service applies (its "instance")

Each service ships an `observability/` folder that the platform loads at startup:

- `dashboards/*.json`: a service dashboard (provisioned into Grafana). It contains:
  - golden signals: rate, errors, duration
  - domain metrics
  - links to logs and traces
- `alerts/*.yaml`: alert rules for its business and service-level alerts.
- The service also documents its domain metrics and business alerts in its domain note under `docs/project/`.

## Conventions

**Metrics**
- Prefix `yl_<service>_`, with snake_case names and units in the name (`_seconds`, `_total`, `_bytes`).
- Labels are limited to low-cardinality values (`source`, `country`, `rule`, `status`). Never use dates or ids as labels.
- Mandatory domain signals:
  - throughput (e.g. `yl_ingestion_observations_loaded_total`)
  - freshness (e.g. `yl_ingestion_source_last_success_timestamp_seconds`)
  - outcome (e.g. `yl_processing_quality_checks_total{status}`)
- **Business alerts as metrics:**
  - Each service evaluates its business alert conditions itself, because it knows their meaning.
  - It exposes each condition through `GET /v1/alerts` and as the gauge `yl_<service>_alert_active{alert}`.
  - Grafana routes that gauge to notifications. One source of truth, two views.

**Logs**
- Structured JSON to stdout only (12-factor). The collector ships them to Loki.
- Mandatory fields: `timestamp`, `level`, `service`, `version`, `trace_id`, `span_id`, `event`, plus context (`run_id`, `curve_id`).
- Levels:
  - `ERROR`: needs action
  - `WARNING`: degraded but handled
  - `INFO`: business events and lifecycle
  - `DEBUG`: off in live
- Never log secrets or payload dumps. Raw payloads live in `ING`, not in logs.

**Traces**
- W3C `traceparent` propagation across all HTTP calls, including Airflow tasks. This replaces a custom correlation id.
- The trace id is also set as the Oracle `CLIENT_IDENTIFIER` and in `DBMS_APPLICATION_INFO`, so database sessions can be matched to traces.

**Alerting**
- **System alerts (platform):**
  - service down / readiness failing
  - error rate and latency above SLO
  - Oracle tablespace or session limits
  - Airflow task failures
  - VM disk / memory
- **Business alerts (per service):** e.g. source late (freshness SLO breached), volume out of range, schema drift, delivery or slice quarantined, blocking quality rule failed, mart publish aborted, recalculation failed.
- **Data-safety alerts (platform):** backup missing or older than 26 h.
- **Notifications:** Grafana contact point (email or chat webhook, both free). Every alert links to its dashboard and runbook.

## Retention and exposure (demo)

- Metrics 15 days, logs 7 days, traces 3 days. These limits keep the VM within its resources.
- Grafana is reachable via SSH tunnel. An optional read-only public dashboard (anonymous viewer) can be enabled for showcasing.
- Business transparency data is part of the product and is visible in the frontend.
