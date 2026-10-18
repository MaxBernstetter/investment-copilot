# ADR 0004: Interface models are the only shared code

**Status:** Accepted · 2026-10-18

## Context
Services must be fully separated, but they need a common definition of the data they exchange.

## Decision
A `contracts/` package holds versioned Pydantic interface models and the OpenAPI document per service. It is the **only** code that services may share. It contains data shapes and validation only, with no behaviour. Services map contract models to their own domain models at the adapter boundary. The frontend uses a TypeScript client generated from the `access` OpenAPI document.

## Consequences
- Interfaces are explicit, versioned and reviewable. A contract change visibly triggers all consumers in CI.
- Some duplication between contract and domain models, accepted as the price of independent domains.
- Separation is enforced by import-linter, separate uv projects and contract tests.

Rejected: a shared "common" library with utilities or domain types. It becomes a coupling point.
