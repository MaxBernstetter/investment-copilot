# ADR 0011: Validation gates and write–audit–publish

**Status:** Accepted · 2026-10-18

## Context
Quality checks only add value if bad data is stopped before it reaches consumers. Without a defined gate, data failing a check could still flow into marts and the API, and mart rebuilds could expose partially built content.

## Decision
- Quality rules have a severity (`block`, `warn`, `info`).
- `block` failures quarantine the affected slice (curve × date range) and stop it from being published downstream.
- `warn` failures publish the data but flag it in response metadata.
- Marts are built with **write–audit–publish**: build into staging, validate, then swap in atomically via Oracle partition exchange.
- Bad records are never discarded silently. They are quarantined with reason, stage and timestamp, and alerted.

## Consequences
- Consumers only see data that passed blocking checks, or data explicitly flagged.
- A blocked slice can delay availability; freshness alerts make this visible.
- Requires partitioned mart tables and staging tables per mart.
