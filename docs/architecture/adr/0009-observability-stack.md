# ADR 0009: OpenTelemetry and a self-hosted Grafana stack

**Status:** Accepted · 2026-10-18

## Context
Every service is responsible for its own transparency ([[0008-transparency-per-service]]). Services need one monitoring and logging setup to plug into, with metrics, logs, traces and alerting. It must be free, run on the demo VM and locally, and not require shared code between services.

## Decision
- **Instrumentation:** OpenTelemetry SDK in every service, configured via `OTEL_*` environment variables; structured JSON logs to stdout; W3C trace context propagation.
- **Pipeline:** one OpenTelemetry Collector per stack.
- **Backends:** Prometheus (metrics), Loki (logs), Tempo (traces), Grafana (dashboards and alerting), all in the Compose stack.
- **Platform sources:** an Oracle exporter (Oracle's observability exporter), Airflow's native OpenTelemetry metrics, Caddy metrics, node and container exporters.
- **Per service:** dashboards and alert rules live as code in the service's `observability/` folder and are provisioned into Grafana.

## Consequences
- Vendor-neutral: switching to a managed backend (e.g. Grafana Cloud free tier) only changes the collector config.
- Same setup locally and live; dashboards and alerts are versioned with the code they describe.
- Adds about 1–1.5 GB RAM on the VM; retention is capped for the demo.
- Uses the de facto industry standard (OpenTelemetry, Grafana), matching "operational readiness" in the target role.

Rejected:
- Grafana Cloud only. Free, but an external dependency and not reproducible locally. It stays a swap option.
- ELK. Heavier and uses more resources.
