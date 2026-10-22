# Plausibility thresholds

How the plausibility rules of [#31](https://github.com/MaxBernstetter/yield-lens/issues/31) are set for the ECB curves, and how to re-derive them. The rules flag a value; in phase 2 they never block it (`warn` or `info` only).

## Rules

| Rule | Severity | Flags a value when | AAA hits (2004-09-06 to 2026-10-18) | All-issuer hits (2004-09-06 to 2026-10-20) |
|---|---|---|---|---|
| Range | `warn` | it lies outside −2.00 % … 8.00 % | none | none |
| Jump | `info` | it moved more than 25 bp against the previous valid date with a value of the same maturity | 41 values on 20 days | 93 values on 51 days |
| Jump | `warn` | it moved more than 50 bp | 2 values: 3M on 2008-10-07 (+94 bp), 30Y on 2008-12-04 (+56 bp) | 3 values: 3M on 2008-10-08 (−66 bp), 30Y on 2009-01-23 (+52 bp), 30Y on 2010-10-15 (−88 bp) |

The thresholds are configuration per curve, next to the curve's calendar and expected maturities (see [[03-quality-checks]]). The simulated curve `ecb-aaa-spot-sim` uses the real curve's thresholds, so a scenario's bad value is flagged like real data would be. Values exactly at a threshold (25 bp, 50 bp, −2.00 %, 8.00 %) are not flagged. The all-issuer curve `ecb-all-spot` has its own thresholds with the same values; see [[#All-issuer curve]].

## Data and method

- **Data:** the full published ECB euro area AAA spot curve: 11 maturities (3M to 30Y), 5,654 business days each from 2004-09-06 to 2026-10-18, 62,183 daily changes. Values in percent, as published.
- **Daily change:** the absolute difference to the previous valid date with a value of the same maturity, in basis points. Weekends and TARGET holidays have no value, so a change after a holiday spans the gap; this is how the rule will compare in operation, too.
- **Statistics:** per maturity the minimum and maximum value and the percentiles P50, P99, P99.9 and maximum of the daily changes (linear interpolation), and for candidate jump thresholds the number of values and days above them.
- **Choice:** a threshold should flag data errors and genuine extremes, not ordinary market days. A `warn` should be so rare in real data that it almost always means a data problem; an `info` should mark real stress days (about once a year) without noise.

## Results

| Maturity | Min % | Max % | P50 bp | P99 bp | P99.9 bp | Max bp |
|---|---|---|---|---|---|---|
| 3M | −0.930 | 4.325 | 0.9 | 8.8 | 21.0 | 94.0 |
| 6M | −0.915 | 4.357 | 0.8 | 8.4 | 16.8 | 30.8 |
| 1Y | −0.913 | 4.540 | 1.0 | 10.3 | 19.6 | 39.7 |
| 2Y | −0.971 | 4.714 | 1.4 | 13.6 | 22.9 | 43.5 |
| 3Y | −1.002 | 4.738 | 1.7 | 13.9 | 24.9 | 38.5 |
| 5Y | −0.996 | 4.730 | 2.1 | 13.4 | 23.7 | 31.2 |
| 7Y | −0.936 | 4.736 | 2.3 | 12.9 | 21.2 | 28.3 |
| 10Y | −0.815 | 4.776 | 2.3 | 13.1 | 20.8 | 26.5 |
| 15Y | −0.628 | 4.872 | 2.4 | 13.6 | 21.3 | 27.0 |
| 20Y | −0.515 | 4.985 | 2.4 | 14.2 | 22.1 | 25.0 |
| 30Y | −0.432 | 5.175 | 2.5 | 15.1 | 24.3 | 56.4 |
| **All** | **−1.002** | **5.175** | | **13.1** | **22.8** | **94.0** |

| Candidate jump threshold | Values above | Days | Share of changes | Years |
|---|---|---|---|---|
| > 20 bp | 105 | 42 | 0.169 % | 2008–2011, 2015, 2016, 2020, 2022, 2023, 2025, 2026 |
| **> 25 bp (info)** | 41 | 20 | 0.066 % | 2008–2010, 2015, 2022, 2023, 2025 |
| > 30 bp | 15 | 7 | 0.024 % | 2008–2010, 2023 |
| > 40 bp | 4 | 4 | 0.006 % | 2008, 2023 |
| **> 50 bp (warn)** | 2 | 2 | 0.003 % | 2008 |

## Why these thresholds

- **Range −2.00 % … 8.00 %:** the history spans −1.00 % to 5.18 %. The band leaves about one percentage point below the deepest negative rates and about three above the highest values, so a higher-rate regime does not flag ordinary data, while a decimal slip (for example 26.40 instead of 2.64) does.
- **Jump > 25 bp as `info`:** above P99.9 for every maturity; 20 days in 22 years, all real stress days (Lehman 2008, the euro crisis, 2015, the 2022 rate turn, SVB in March 2023). Worth pointing out, not an error.
- **Jump > 50 bp as `warn`:** exceeded twice in 22 years, both at the height of the 2008 crisis. A move this large is almost always a data problem.
- **One threshold for all maturities:** the short end has rarer but larger spikes (3M max 94 bp) and the long end more frequent medium moves. A single pair of thresholds keeps the rule simple to explain; per-maturity thresholds are a phase-3 refinement if the dashboard shows too many `info` flags at one end.

## All-issuer curve

Derived for `ecb-all-spot` (the ECB all-issuer spot curve, G_N_C) with `--source ecb`: 11 maturities (3M to 30Y), 5,656 business days each from 2004-09-06 to 2026-10-20, 62,205 daily changes. Values in percent, as published.

| Maturity | Min % | Max % | P50 bp | P99 bp | P99.9 bp | Max bp |
|---|---|---|---|---|---|---|
| 3M | −0.833 | 4.291 | 0.9 | 12.6 | 33.1 | 66.1 |
| 6M | −0.791 | 4.350 | 0.9 | 11.1 | 27.2 | 32.4 |
| 1Y | −0.741 | 4.560 | 1.1 | 14.7 | 30.8 | 43.0 |
| 2Y | −0.665 | 4.769 | 1.6 | 15.8 | 33.6 | 43.0 |
| 3Y | −0.641 | 4.814 | 1.9 | 15.6 | 28.7 | 39.4 |
| 5Y | −0.562 | 4.810 | 2.2 | 14.5 | 25.2 | 34.8 |
| 7Y | −0.457 | 4.826 | 2.3 | 14.1 | 23.4 | 33.5 |
| 10Y | −0.264 | 5.069 | 2.4 | 14.0 | 21.5 | 36.6 |
| 15Y | 0.037 | 5.451 | 2.4 | 14.1 | 23.0 | 34.2 |
| 20Y | 0.260 | 5.644 | 2.4 | 14.5 | 22.0 | 32.7 |
| 30Y | 0.521 | 5.838 | 2.4 | 16.4 | 34.5 | 88.1 |
| **All** | **−0.833** | **5.838** | | **14.6** | **28.0** | **88.1** |

| Candidate jump threshold | Values above | Days | Share of changes | Years |
|---|---|---|---|---|
| > 20 bp | 200 | 93 | 0.322 % | 2008–2013, 2015, 2018–2020, 2022–2026 |
| **> 25 bp (info)** | 93 | 51 | 0.150 % | 2008–2012, 2015, 2018, 2020, 2022, 2023, 2025 |
| > 30 bp | 50 | 33 | 0.080 % | 2008–2012, 2015, 2018, 2020, 2022, 2023 |
| > 40 bp | 7 | 7 | 0.011 % | 2008–2012 |
| **> 50 bp (warn)** | 3 | 3 | 0.005 % | 2008–2010 |

Why the same values as the AAA curve:

- **Range:** the history spans −0.83 % to 5.84 %, inside −2.00 % … 8.00 %, more than one percentage point above the low bound and more than two below the high one. No value is flagged.
- **Jump > 25 bp as `info`:** 51 days in 22 years, about 2.3 a year, under the "about three a year" revisit rule. The days are stress periods as on the AAA curve.
- **Jump > 50 bp as `warn`:** 3 days, 2008 to 2010. One is a long-end fitting artefact (30Y on 2010-10-15, −88 bp), which is exactly what `warn` is for; the other two are the 3M move on 2008-10-08 and the 30Y move on 2009-01-23.
- **Same values on both ECB curves:** flags stay comparable when the two curves are overlaid in the explorer. The texts are curve-specific, because they cite this curve's own range and counts.

## How users see it

Every flag in the explorer carries a short explanation that states the rule and the evidence. The texts are configured per curve; for the ECB AAA spot curve (and `ecb-aaa-spot-sim`) they are:

- **Range (warn):** "Outside the plausible range of −2.00 % to 8.00 %. ECB AAA spot yields stayed between −1.00 % and 5.18 % since 2004."
- **Jump (info):** "Moved more than 25 bp since the previous business day. This happened on 20 days since 2004, all in market stress."
- **Jump (warn):** "Moved more than 50 bp since the previous business day. This happened on only 2 days since 2004 (autumn 2008); check the source data."
- **Missing date (warn):** "No value was published for this TARGET business day."
- **Missing maturity (warn):** "No value for this maturity on a TARGET business day on which other maturities have one."

For the all-issuer curve `ecb-all-spot`:

- **Range (warn):** "Outside the plausible range of −2.00 % to 8.00 %. ECB all-issuer spot yields stayed between −0.83 % and 5.84 % since 2004."
- **Jump (info):** "Moved more than 25 bp since the previous business day. This happened on 51 days since 2004, mostly in market stress."
- **Jump (warn):** "Moved more than 50 bp since the previous business day. This happened on only 3 days since 2004 (2008 to 2010); check the source data."

The missing-date and missing-maturity texts are the same as for the AAA curve.

The quality dashboard links to this note for the full method. The rule configuration in the processing service names this note in a comment next to each threshold.

## Re-deriving

1. Load the full history into a local stack: `task dev:up`, then `task dev:seed START=2004-09-06` (about 23 polite requests to the ECB). Or skip the stack and add `--source ecb` in step 2 (one request to the ECB, for `ecb-aaa-spot` or `ecb-all-spot`).
2. Run `python3 src/scripts/plausibility_thresholds.py` (standard library only; `--access-url` and `--curve` are optional; `--source ecb` reads the history from the ECB data API instead of the access API).
3. Compare with the tables above. Revisit the thresholds when a new curve is added, when the range comes within half a percentage point of a bound, or when `info` flags appear on more than about three days a year. A new curve gets its own thresholds, calendar, expected maturities and explanation texts in `RULES_BY_CURVE`.

Related: [[README|Data processing]], [#31](https://github.com/MaxBernstetter/yield-lens/issues/31), [#38](https://github.com/MaxBernstetter/yield-lens/issues/38), [#65](https://github.com/MaxBernstetter/yield-lens/issues/65)
