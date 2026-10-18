# ADR 0008: Transparency is a per-service capability, not a domain

**Status:** Accepted · 2026-10-18 · Amends [[0002-service-per-bounded-context]]

## Context
The original design had a separate `transparency` service collecting runs, lineage, diffs, impact and alerts from all others. It had no language of its own and only aggregated facts owned by other domains. It also required every service to push events to a central store.

## Decision
Remove `transparency` as a service and schema. **Each service is transparent on its own**: it stores and exposes its business transparency data (runs, lineage, quality, diffs, impact), its business alerts, and its system telemetry. Business transparency data is exposed through a common interface (`contracts/transparency/v1`). Features move to their owners:
- ingestion: runs, late/missing/revised detection
- persistence: lineage per value, knowledge-state diffs
- processing: quality results, anomalies, derived lineage, recalculation impact

## Consequences
- Data stays with the logic that understands it; there is no central coupling point and no event push.
- A uniform interface keeps transparency consistent across services.
- Cross-service lineage must be assembled by following upstream refs (done by `access`).
- The platform must provide a common monitoring setup (see [[0009-observability-stack]]).
