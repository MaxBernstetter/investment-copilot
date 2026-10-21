# ADR 0020: Derived measures computed on read

**Status:** Accepted · 2026-10-21

## Context

Consumers need spreads (the slope), curvature and inversion per valid date for a curve. These are simple functions of the published values, and their quality depends on the same as-of knowledge state as the curve. Phase 3 of the project can store derived data, so the question is where the measures live and when they are computed.

## Options

| Option | For | Against |
|---|---|---|
| **(a) Compute on read in processing** | Nothing to keep in sync; as-of reads reproduce the same answer from the bitemporal inputs; the method is one versioned pure function | Work per request, bounded by the 3660-day range |
| (b) Store a PROC mart per check run | Fast reads; a fixed snapshot per run | A second copy of the values to keep correct; a mart per method change; as-of needs its own versioning |
| (c) Compute in access | Fewer hops for the browser | Access would own calculation, which belongs to processing in the context map |
| (d) Compute in the frontend | No backend change | Every client repeats the definitions; no shared method version; no reproducible as-of answer |

## Decision

Option (a). Processing computes the measures on read with one pure function per point and one use case. Nothing is stored. The method is identified by `method_version`. Inputs and their quality are read at one effective as-of time (the requested time capped at the knowledge horizon). Access stays a relay that adds attribution and caching.

## Consequences

- As-of reproducibility follows from the bitemporal inputs and the knowledge clock: a read at `T` gives the same measures for as long as the inputs known at `T` do not change.
- The cost per request is bounded by the 3660-day range and the four input maturities; no interpolation or configurable method keeps the calculation small.
- Storing measures later (a mart) needs a new ADR, once a measured need exists. Until then the table set does not grow.
- A change to a formula or the input set bumps `method_version` and is documented in [[04-derived-measures]].
