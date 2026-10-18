# Features

Previous: [[01-problem-solution]]

Features are grouped by domain, ordered along the data and usage flow. Phase numbers refer to the phasing in [[01-problem-solution]].

```
Ingestion → Persistence → Processing → Access (API) → Frontend
    └───────────┴─────────────┴── each transparent: business data · alerts · system data
                                   └──▶ 03 Observability platform (shared setup)
```

| # | Domain | Role in the flow |
|---|---|---|
| 00 | Data Ingestion | Get source data in, reliably and repeatably |
| 01 | Data Persistence | Store every value with its full history |
| 02 | Data Processing | Validate, calculate and prepare data |
| 03 | Observability (cross-cutting) | The monitoring setup every service applies; not a domain |
| 04 | Data Access | Serve data to systems and the UI |
| 05 | User Frontend | Let people explore, compare and trace |
| – | Cross-cutting | Engineering practices |

Changes to your original set:
- **Data Access (04)** is new, because the API serves both downstream systems and the frontend, and fits neither the processing nor the frontend domain. User Frontend moves from 04 to 05.
- The former "insight layer" and "operations" are distributed across the domains instead of standing alone.
- **Transparency is not a domain.** Each service is transparent on its own: it exposes its business data (runs, lineage, quality, diffs, impact), its alerts, and its system data. Slot 03 holds the shared observability platform. See `docs/architecture/10-observability.md`.

---

## 00 Data Ingestion

Bring source data into the platform.

| Feature | Phase |
|---|---|
| Daily load from public sources for one country | 1 |
| Normalization to a common maturity grid, units and conventions | 1 |
| Scheduled pipelines with retries | 1 |
| Idempotent reruns and date-range backfill | 1 |
| Raw source payload retained for traceability | 1 |
| Detection of late, missing and revised source data | 2 |
| Revision lookback: re-fetch a window of past days per source to catch silent revisions | 2 |
| Source contract per source (payload schema, publication time, expected volume) with schema-drift detection and quarantine | 2 |
| Source registry and source calendars (versioned reference data) | 2 |
| Scenario mechanism: inject corrections, late data, gaps and bad values, labelled as simulated | 2 |
| Additional countries and sources | 3 |

**Transparency**

| Feature | Phase |
|---|---|
| Run history of loads: status, duration, record counts | 2 |
| Business alerts: failed, partial, late or missing deliveries | 2 |
| Metrics, logs, traces and dashboard (applies the observability setup) | 2 |

## 01 Data Persistence

Store every value with its history.

| Feature | Phase |
|---|---|
| Valid time and knowledge time on every value | 1 |
| Versioning instead of overwriting (corrections, late data) | 1 |
| As-of retrieval: "the curve for date X as known on date Y" | 1 |
| Correction reason and origin recorded with each version | 2 |
| Source, ingestion run and status recorded per value | 2 |
| Distinction between published and model-estimated values | 2 |
| Storage for derived curves, including method and method version | 3 |
| Curve definitions and maturity grid (versioned reference data) | 1 |
| Concurrency-safe writes for overlapping runs | 2 |
| Replay: rebuild core from raw payloads for a date range and normalization version | 3 |

**Transparency**

| Feature | Phase |
|---|---|
| Lineage per value: source, run, version history | 2 |
| Diff between two knowledge states, with reasons | 2 |
| Metrics, logs, traces and dashboard (applies the observability setup) | 2 |

## 02 Data Processing

Validate, calculate and prepare data.

**Validation (data quality)**

| Feature | Phase |
|---|---|
| Completeness checks (missing dates and maturities) | 2 |
| Plausibility checks (value ranges, day-over-day jumps) | 2 |
| Quality status assigned to each value | 2 |
| Validation gates: rule severity (block / warn / info); blocked slices quarantined and not published | 2 |
| Market calendars and conventions (versioned reference data) | 2 |
| Curve sanity checks (implausible shapes, odd forward rates) | 3 |
| Cross-source consistency checks | 3 |

**Calculation**

| Feature | Phase |
|---|---|
| Derived measures: spreads, slope, curvature, inversion flag | 3 |
| Derived curves: fit and interpolate to standard maturities | 3 |
| Forward rates | 3 |
| Historical recalculation on methodology change, producing a new versioned series | 3 |

**Preparation**

| Feature | Phase |
|---|---|
| Data marts: curves (current and as-of), spreads and slope, quality | 3 |
| Write–audit–publish for marts (build, validate, atomic swap) | 3 |
| Anomaly detection on curve movements (level, slope, curvature) | 4 |

**Transparency**

| Feature | Phase |
|---|---|
| Quality results per source, country and day (rule, outcome, affected values) | 2 |
| Business alerts: failed quality rules, failed recalculations | 2 |
| Metrics, logs, traces and dashboard (applies the observability setup) | 2 |
| Lineage for derived values: inputs and method version | 3 |
| Recalculation impact: what changed and by how much | 3 |
| Anomaly findings as alerts | 4 |

## 03 Observability (cross-cutting)

The shared monitoring and logging setup that every service applies. Not a domain: it owns no business data.

| Feature | Phase |
|---|---|
| Transparency interface contract (runs, lineage, alerts) for all services | 2 |
| Telemetry conventions: metric naming, log fields, trace propagation | 2 |
| Observability stack: OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana | 2 |
| Platform alerts (service down, error rate, Oracle, Airflow, VM) and notification channel | 2 |
| Provisioning of per-service dashboards and alert rules | 2 |
| Runbook for late, malformed or revised data and for platform alerts | 2 |
| Data observability pillars: freshness SLOs, volume ranges, schema drift, distribution, lineage | 2 |
| Backup and restore: daily exports to object storage, monitored, restore tested | 2 |
| OpenLineage run and dataset lineage (Airflow and jobs) | 3 |

## 04 Data Access

Serve data to downstream systems and the frontend.

| Feature | Phase |
|---|---|
| REST API for curves and time series | 2 |
| As-of parameter on every data endpoint | 2 |
| Version, quality and lineage metadata in responses | 2 |
| Transparency data from all services (runs, quality, alerts), with cross-service lineage | 2 |
| Access to marts and derived measures | 3 |
| Stable, versioned API contract | 3 |
| Grounded question answering: natural-language questions answered from platform data, citing exact versions | 4 |

## 05 User Frontend

Let people explore, compare and trace.

| Feature | Phase |
|---|---|
| View curves by country and date | 1 |
| Overlay curves from different dates or countries | 1 |
| Time series per maturity | 1 |
| Time-travel control (as-of knowledge time) | 1 |
| Version history and lineage view per value | 2 |
| Quality dashboard and pipeline run view | 2 |
| Difference view between two knowledge states | 2 |
| Published vs. derived curve comparison | 3 |
| Recalculation impact view | 3 |
| Ask-the-data interface with cited sources | 4 |

---

## Cross-cutting: Engineering Foundation

Delivered from phase 1.

| Feature |
|---|
| Automated tests (unit, data, end-to-end for the corrected-yield scenario) |
| CI/CD pipeline |
| Containerized, reproducible local environment |
| Documentation in `docs/` kept consistent with the implementation |
