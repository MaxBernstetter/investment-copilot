# ADR 0002: One service and one schema per bounded context

**Status:** Accepted · 2026-10-18 · Amended by [[0008-transparency-per-service]] (no separate transparency context)

## Context
The domains (ingestion, persistence, processing, access, frontend) have distinct models and lifecycles. The requirement is that each runs separately and that code is fully separated.

## Decision
Each domain is a **bounded context implemented as its own service** in the monorepo, with its own project, container, tests and Oracle schema (with its own DB user, and no cross-schema grants). Data crosses contexts only through published interfaces.

## Consequences
- Clear ownership and independent deployability; contexts can evolve and scale separately.
- No shortcuts via shared tables. Bulk reads need explicit bulk interfaces (Arrow streams).
- More moving parts than a modular monolith: several containers, inter-service contracts, contract tests.

Rejected: a modular monolith with a shared schema. It is simpler, but it violates the separation requirement and hides coupling.
