# ADR 0019: Quality results as of checked knowledge time

**Status:** Accepted · 2026-10-20

## Context

Processing stores the outcome of each quality check run under the natural key `(curve_id, valid_from, valid_to, checked_as_of)`, where `checked_as_of` is the persistence knowledge time used for the observations that were checked. Consumers need a stable rule for which run applies to a business day when they read at knowledge time `T`, including after later checks or reruns at the same knowledge time.

## Decision

- A **check run** is identified by `(curve_id, valid_from, valid_to, checked_as_of)`. Recording the same key again replaces that run's day, value and finding rows (idempotent at a fixed knowledge time).
- For a read at `as_of = T`, each `valid_date` in the requested range is assessed from the run with the greatest `(checked_as_of, check_run_id)` among runs where `checked_as_of <= T` and the run has a `checked_day` row for that date.
- Runs with `checked_as_of > T` are invisible to the read. A later knowledge time can change the assessment of a day until `T` catches up.
- `unchecked` is not stored; it is the absence of a qualifying run for that day on the read side.

## Consequences

- Time-travel and access assembly can pin quality to the same persistence `as_of` without a separate quality clock.
- A value can keep an older jump or range status until the next check that includes it; the daily check after each load limits how long that window lasts.
- PROC read procedures (`get_checked_days`, `get_findings`, `get_value_quality`) implement the rule in one place; API layers map the result to contracts.
