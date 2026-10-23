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

## US Treasury par yield curve

Derived for `ust-par` (the US Treasury daily par yield curve, grid 2) with `plausibility_thresholds.py --source ust` from the Treasury's yearly CSV files, 1990 to 2026: 14 tenors (1M to 30Y), 9,208 published days from 1990-01-02 to 2026-10-22, 99,866 daily changes. Values in percent, as published.

**Status of the figures:** a live run of the script on 2026-10-23 got no response from the Treasury site (the connection stayed open for about nine minutes; the run was stopped without output). The tables below are the script's output on the 37 yearly files fetched earlier the same day with the same URL pattern (one request per year, HTTP 200 each). They reproduce the counts of the hand-made derivation of the same day. The thresholds of `UST_PAR` in `rule_config.py` therefore stay **provisional** until a live run completes.

| Tenor | Min % | Max % | P50 bp | P99 bp | P99.9 bp | Max bp |
|---|---|---|---|---|---|---|
| 1M | 0.000 | 6.020 | 1.0 | 26.9 | 69.1 | 106.0 |
| 1.5M | 3.650 | 4.530 | 1.0 | 6.8 | 10.9 | 13.0 |
| 2M | 0.000 | 5.610 | 1.0 | 15.0 | 22.0 | 27.0 |
| 3M | 0.000 | 8.260 | 1.0 | 17.0 | 47.0 | 81.0 |
| 4M | 3.580 | 5.640 | 1.0 | 10.0 | 19.0 | 21.0 |
| 6M | 0.020 | 8.490 | 1.0 | 15.0 | 32.6 | 75.0 |
| 1Y | 0.040 | 8.640 | 2.0 | 16.0 | 33.8 | 60.0 |
| 2Y | 0.090 | 9.050 | 3.0 | 19.0 | 33.0 | 57.0 |
| 3Y | 0.100 | 9.110 | 3.0 | 19.0 | 32.0 | 50.0 |
| 5Y | 0.190 | 9.100 | 3.0 | 19.0 | 29.0 | 46.0 |
| 7Y | 0.360 | 9.120 | 3.0 | 19.0 | 28.8 | 53.0 |
| 10Y | 0.520 | 9.090 | 3.0 | 18.0 | 26.6 | 51.0 |
| 20Y | 0.870 | 8.300 | 3.0 | 16.0 | 25.0 | 35.0 |
| 30Y | 0.990 | 9.180 | 3.0 | 16.0 | 27.8 | 86.0 |
| **All** | **0.000** | **9.180** | | **18.0** | **34.0** | **106.0** |

| Candidate jump threshold | Values above | Days | Share of changes | Years |
|---|---|---|---|---|
| > 20 bp | 709 | 269 | 0.710 % | 1990 to 2011, 2013, 2016 to 2018, 2020 to 2025 |
| **> 25 bp (info)** | 278 | 130 | 0.278 % | 1990 to 1992, 1994 to 1998, 2000 to 2009, 2011, 2017, 2020, 2022 to 2024 |
| > 30 bp | 159 | 81 | 0.159 % | 1991, 1992, 1994 to 1996, 1998, 2000, 2001, 2005 to 2009, 2017, 2020, 2022, 2023 |
| > 40 bp | 67 | 37 | 0.067 % | 1994, 1998, 2000, 2001, 2006 to 2009, 2023 |
| **> 50 bp (warn)** | 31 | 24 | 0.031 % | 1998, 2000, 2001, 2006 to 2009, 2023 |

Why these thresholds:

- **Range −0.50 % … 10.00 %:** the history spans 0.00 % to 9.18 %, so no value is flagged. The band leaves 0.5 pp below zero and about 0.8 pp above the highest value.
- **Jump > 25 bp as `info`:** 130 days in about 37 years, about 3.5 a year, slightly above the "about three a year" revisit rule. 162 of the 278 values are from the 2000s and 69 are the 1M bill (2007 to 2008 and 2023 among them). The script reproduces the counts; the rule stays provisional until a live run completes.
- **Jump > 50 bp as `warn`:** 24 days, all in stress periods (1998, 2000, 2001, 2006 to 2009, 2023), except one artefact: 30Y on 2006-02-09 (+86 bp), the first value after the 2002-02-19 to 2006-02-08 gap, compared with 2002-02-15. The backfill will show this one `warn`; it is a known false positive of the gap, not a data error.
- **Calendar and maturities:** the bond market closures (Good Friday, unscheduled closures) and the column introductions are in the calendar and the expected maturities, not the thresholds (see [[03-quality-checks]]).

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

For the US Treasury curve `ust-par`:

- **Range (warn):** "Outside the plausible range of −0.50 % to 10.00 %. US Treasury par yields stayed between 0.00 % and 9.18 % since 1990."
- **Jump (info):** "Moved more than 25 bp since the previous business day. This happened on 130 days since 1990, many of them in stress periods."
- **Jump (warn):** "Moved more than 50 bp since the previous business day. This happened on only 24 days since 1990 (1998, 2000, 2001, 2006 to 2009 and 2023), mostly in market stress; check the source data."

The quality dashboard links to this note for the full method. The rule configuration in the processing service names this note in a comment next to each threshold.

## Re-deriving

1. Load the full history into a local stack: `task dev:up`, then `task dev:seed START=2004-09-06` (about 23 polite requests to the ECB). Or skip the stack and add `--source ecb` in step 2 (one request to the ECB, for `ecb-aaa-spot` or `ecb-all-spot`).
2. Run `python3 src/scripts/plausibility_thresholds.py` (standard library only; `--access-url` and `--curve` are optional; `--source ecb` reads the history from the ECB data API instead of the access API).
3. For the US Treasury curve run `python3 src/scripts/plausibility_thresholds.py --source ust` instead (one request per year from 1990, 3 s apart, about two minutes when the site answers; no stack needed).
4. Compare with the tables above. Revisit the thresholds when a new curve is added, when the range comes within half a percentage point of a bound, or when `info` flags appear on more than about three days a year. A new curve gets its own thresholds, calendar, expected maturities and explanation texts in `RULES_BY_CURVE`.

Related: [[README|Data processing]], [#31](https://github.com/MaxBernstetter/yield-lens/issues/31), [#38](https://github.com/MaxBernstetter/yield-lens/issues/38), [#65](https://github.com/MaxBernstetter/yield-lens/issues/65)
