# ADR 0007: Backend hosting on OCI Always Free

**Status:** Accepted · 2026-10-18

## Context
The live demo must run the full backend (Oracle, the services, Airflow, the observability stack) at no cost. Typical free PaaS tiers can't host Oracle or this many containers.

## Decision
Run the backend as one Docker Compose stack on an **Oracle Cloud Infrastructure Always Free Ampere A1 VM** (4 OCPU, 24 GB RAM, ARM64), behind **Caddy** with automatic HTTPS. Only `access` is publicly reachable.

## Consequences
- Free and sufficient for the demo; shows cloud and container operations. Oracle stays consistent between local and live.
- ARM64 means all images must be built multi-arch.
- A single VM is a single point of failure, which is acceptable for a demo.
- Sign-up needs card verification. A1 capacity can be scarce in some regions.
- Upgrade path: Autonomous Database and container orchestration (see [[08-scalability]]).

Rejected: Fly.io/Render. Not free at this size, and they can't host Oracle easily.
