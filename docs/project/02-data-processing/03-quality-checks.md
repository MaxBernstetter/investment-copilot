# Quality checks

The rules that check the published values of a curve, the severities and statuses they produce, and where their configuration lives. The thresholds and how they were derived are in [[01-plausibility-thresholds]]. The rules belong to the processing service ([[02-processing-service]]). The rule set version is `1`.

## Rules

| Rule | Severity | Flags when | Scope |
|---|---|---|---|
| `range` | `warn` | the value is strictly below the range minimum or strictly above the maximum (−2.00 % to 8.00 % for the ECB AAA spot curve) | one value |
| `jump` | `info` | the move against the previous value of the same maturity is strictly more than 25 bp | one value |
| `jump` | `warn` | the move is strictly more than 50 bp | one value |
| `missing-date` | `warn` | a TARGET business day has no value at any maturity | one day |
| `missing-maturity` | `warn` | a TARGET business day has values for some maturities, but a grid maturity has none (not reported on a missing-date day) | one day and maturity |

- **Comparisons are strict.** A value exactly on a threshold is not flagged.
- **Jumps** compare a value with the previous valid date that has a value for the same maturity, so a gap such as a weekend or a TARGET holiday is spanned. A previous value more than 31 days back is not compared.
- **Weekends and TARGET holidays** have no values and are not flagged.
- **Thresholds** are configuration per curve in the processing code. The simulated curve `ecb-aaa-spot-sim` uses the thresholds of the real curve.
- **Explanations** are fixed texts per flag. They match "How users see it" in [[01-plausibility-thresholds]].

## Completeness

Completeness checks run over the TARGET business days in the checked range and the curve's grid maturities.

- A day with **no value at any maturity** produces one `missing-date` finding for that day (no `missing-maturity` findings on the same day).
- A day with **values for some maturities** produces one `missing-maturity` finding per grid maturity without a value.
- **Weekends and TARGET holidays** are not in the business-day set and are never flagged.

The calendar logic matches orchestration's TARGET schedule (see `processing.domain.calendar`).

## Severities

- `warn`: almost always a data problem.
- `info`: a real market move worth pointing out.

There are no other severities. Rules never block a value; they only flag it.

## Statuses

- **Value status:** the worst severity of the value's findings (`warn` beats `info`), otherwise `passed`.
- **Day status:** the worst severity over all findings of the day, otherwise `passed`.
- **`unchecked`:** no check result exists yet for the value or day. It appears on the read side only.

## Running a check

A quality check loads the curve grid once from persistence (`GET /v1/curves/{id}/observations` with no query parameters). The `meta.as_of` of that response is the **checked knowledge time** for the whole run: every maturity series in the run is read as of that time.

The requested valid-date range is processed in chunks of at most 366 days. For each chunk and each grid maturity, persistence returns the series from **31 days before the chunk start** through the chunk end (`from` = chunk start − 31d). That lead-in is used only for jump comparisons; value and day statuses are produced only for dates inside the chunk.

If the grid call returns 404, nothing is known about the curve and no results are recorded.

## Storage

Check results live in the PROC schema (Oracle). Each run is keyed by curve, valid range and checked knowledge time (`checked_as_of`). Recording the same key again replaces that run's day statuses, value statuses and findings (idempotent at a fixed knowledge time). A later knowledge time creates a new run.

The processing service writes through the `proc_quality.record_check` PL/SQL procedure as `proc_app` (execute on the package and its input types only; no direct table access). One call stores the run header, all checked days, per-value statuses and findings in set-based inserts.
