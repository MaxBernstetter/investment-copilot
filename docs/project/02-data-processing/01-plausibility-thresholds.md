# Plausibility thresholds

How the plausibility rules of [#31](https://github.com/MaxBernstetter/yield-lens/issues/31) are set, and how to re-derive them. The rules flag a value; in phase 2 they never block it (`warn` or `info` only).

## Rules

| Rule | Severity | Flags a value when | Hits in the history (2004-09-06 to 2026-10-18) |
|---|---|---|---|
| Range | `warn` | it lies outside −2.00 % … 8.00 % | none |
| Jump | `info` | it moved more than 25 bp against the previous valid date with a value of the same maturity | 41 values on 20 days |
| Jump | `warn` | it moved more than 50 bp | 2 values: 3M on 2008-10-07 (+94 bp), 30Y on 2008-12-04 (+56 bp) |

The thresholds are configuration per curve. The simulated curve `ecb-aaa-spot-sim` uses the real curve's thresholds, so a scenario's bad value is flagged like real data would be. Values exactly at a threshold (25 bp, 50 bp, −2.00 %, 8.00 %) are not flagged.

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

## How users see it

Every flag in the explorer carries a short explanation that states the rule and the evidence, for example:

- **Range (warn):** "Outside the plausible range of −2.00 % to 8.00 %. ECB AAA spot yields stayed between −1.00 % and 5.18 % since 2004."
- **Jump (info):** "Moved more than 25 bp since the previous business day. This happened on 20 days since 2004, all in market stress."
- **Jump (warn):** "Moved more than 50 bp since the previous business day. This happened on only 2 days since 2004 (autumn 2008); check the source data."
- **Missing date (warn):** "No value was published for this TARGET business day."
- **Missing maturity (warn):** "No value for this maturity on a TARGET business day on which other maturities have one."

The quality dashboard links to this note for the full method. The rule configuration in the processing service names this note in a comment next to each threshold.

## Re-deriving

1. Load the full history into a local stack: `task dev:up`, then `task dev:seed START=2004-09-06` (about 23 polite requests to the ECB).
2. Run `python3 src/scripts/plausibility_thresholds.py` (standard library only; `--access-url` and `--curve` are optional).
3. Compare with the tables above. Revisit the thresholds when a new curve is added, when the range comes within half a percentage point of a bound, or when `info` flags appear on more than about three days a year.

Related: [[README|Data processing]], [#31](https://github.com/MaxBernstetter/yield-lens/issues/31), [#38](https://github.com/MaxBernstetter/yield-lens/issues/38), [#65](https://github.com/MaxBernstetter/yield-lens/issues/65)
