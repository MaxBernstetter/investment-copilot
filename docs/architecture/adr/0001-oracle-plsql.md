# ADR 0001: Oracle Free 23ai with PL/SQL

**Status:** Accepted · 2026-10-18

## Context
The core of YieldLens is bitemporal, versioned financial data. The target role centres on Oracle schemas, PL/SQL and bitemporal historization. The project must run at no cost.

## Decision
Use **Oracle Database Free 23ai** (container image, amd64/arm64) for all service schemas. Versioning, as-of retrieval and diff logic are implemented as **PL/SQL packages**, which form each schema's API.

## Consequences
- Close match to the target environment; logic sits next to the data.
- Free, but limited to 2 CPU threads, 2 GB RAM and 12 GB user data. That is enough for the demo; growth goes to Autonomous DB or licensed Oracle (see [[08-scalability]]).
- Heavier local footprint than Postgres (~2–3 GB RAM).
- Requires utPLSQL and Liquibase in the toolchain.

Rejected: PostgreSQL. It is lighter, but a weaker match to the role.
