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

The range and jump rules are implemented. The two completeness rules follow with [#30](https://github.com/MaxBernstetter/yield-lens/issues/30).

- **Comparisons are strict.** A value exactly on a threshold is not flagged.
- **Jumps** compare a value with the previous valid date that has a value for the same maturity, so a gap such as a weekend or a TARGET holiday is spanned. A previous value more than 31 days back is not compared.
- **Weekends and TARGET holidays** have no values and are not flagged.
- **Thresholds** are configuration per curve in the processing code. The simulated curve `ecb-aaa-spot-sim` uses the thresholds of the real curve.
- **Explanations** are fixed texts per flag. They match "How users see it" in [[01-plausibility-thresholds]].

## Severities

- `warn`: almost always a data problem.
- `info`: a real market move worth pointing out.

There are no other severities. Rules never block a value; they only flag it.

## Statuses

- **Value status:** the worst severity of the value's findings (`warn` beats `info`), otherwise `passed`.
- **Day status:** the worst severity over all findings of the day, otherwise `passed`.
- **`unchecked`:** no check result exists yet for the value or day. It appears on the read side only.
