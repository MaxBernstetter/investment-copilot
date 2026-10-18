# ADR 0012: Backup and restore for Oracle

**Status:** Accepted · 2026-10-18

## Context
The live demo runs Oracle on a single free VM. Losing the VM would lose the full bitemporal history, which is the core of the product and cannot be re-created from sources (past knowledge states are only known to us).

## Decision
- Daily **Oracle Data Pump** export per schema (`ING`, `CORE`, `PROC`), triggered by an Airflow DAG and uploaded to **OCI Object Storage** (Always Free tier).
- Retention: 7 daily and 4 weekly exports.
- A documented restore procedure, tested regularly by restoring into a local Oracle Free container.
- Backup success and age are monitored; a missing or stale backup is a platform alert.

## Consequences
- Recovery point: up to 24 h. Recovery time: hours. This is acceptable for a demo.
- Raw payloads plus replay allow a partial rebuild even without a backup, but not of past knowledge states.
- At scale: RMAN with archived logs or Autonomous Database automatic backups for point-in-time recovery.
