# Derived measures

Derived measures summarise the shape of a curve on one valid date: the 2Y–10Y and 3M–10Y spreads (the slope), the 2Y–5Y–10Y curvature and whether the curve is inverted. They answer "how steep is the curve today" without the user reading each maturity. Processing computes them on read from the published values, the same way it reads quality. Nothing is stored (see [[0020-derived-measures-computed-on-read]]).

## Definitions

Let `y(m)` be the yield of maturity `m` in percent on the valid date. Each measure is in basis points (1 percentage point = 100 bp) and is not rounded.

| Measure | Formula | Inputs | Unit |
|---|---|---|---|
| `spread_2y_10y` (slope) | `(y(10Y) - y(2Y)) * 100` | 2Y, 10Y | bp |
| `spread_3m_10y` | `(y(10Y) - y(3M)) * 100` | 3M, 10Y | bp |
| `curvature_2y_5y_10y` | `(2 * y(5Y) - y(2Y) - y(10Y)) * 100` | 2Y, 5Y, 10Y | bp |
| `inverted` | `spread_2y_10y < 0` (strict) | 2Y, 10Y | boolean |

A spread of exactly zero is not inverted. The inputs are the four maturities 3M, 2Y, 5Y and 10Y.

## Method version

Every result carries `method_version` (currently `"1"`). Any change to a formula or to the input set bumps the version and is documented on this page. A consumer that stored a result can tell which definition produced it.

## Missing inputs

A missing input is not interpolated and not replaced. Each measure that needs it is `null`:

- without 5Y only the curvature is `null`;
- without 10Y, all three measures and `inverted` are `null`.

The point's `missing` lists the absent maturities in the order 3M, 2Y, 5Y, 10Y.

## Flagged inputs

A measure is still computed when one of its inputs has a quality flag. The point's quality is the worst status over its known inputs, ordered `warn` > `info` > `unchecked` > `passed`. `flagged` lists the maturities whose input status is `warn` or `info`. An `unchecked` input is not flagged, because it has no finding yet. Each input also carries its own `status`, so a consumer can tell "checked and passed" from "not checked".

## As-of

Inputs and their quality are read at one effective as-of time, so a measure reflects the same knowledge state as the curve it is built from. The effective time is the requested `as_of` capped at the knowledge horizon: a time later than the horizon is answered at the horizon. The result's `as_of` is that effective time. Corrections made later are visible only to reads at or after their knowledge time (see [[0017-commit-safe-knowledge-time]] and [[0019-quality-results-as-of-checked-knowledge-time]]).

## Range

A read covers at most 3660 days (`MAX_MEASURES_RANGE`). Longer ranges are rejected.

## Worked example

Scenario base curve on 2026-10-08: 3M 1.95 %, 2Y 1.95 %, 5Y 2.18 %, 10Y 2.61 %.

- `spread_2y_10y` = (2.61 − 1.95) × 100 = **66.00 bp**
- `spread_3m_10y` = (2.61 − 1.95) × 100 = **66.00 bp**
- `curvature_2y_5y_10y` = (2 × 2.18 − 1.95 − 2.61) × 100 = **−20.00 bp**
- `inverted` = **false**

## Implementation

The domain functions are `measure_point` and `worst_input_status` in `processing/domain/measures.py`. They are pure and use `Decimal`. The use case and the public route are added in the following merge requests of [#33](https://github.com/MaxBernstetter/yield-lens/issues/33).
