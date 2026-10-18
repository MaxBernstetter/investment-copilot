# Data Sources

What YieldLens consumes, how it consumes it, and why. The decision itself is [[0016-ecb-aaa-curve-as-first-source]]; the generic rules every source follows are in [[12-data-pipeline#Source access policy]].

Tracked in [#10](https://github.com/MaxBernstetter/investment-copilot/issues/10).

## Summary

| | Phase 1 |
|---|---|
| Source | ECB Data Portal, dataset `YC` (euro area yield curves) |
| Curve | Euro area AAA government bond curve, Svensson model, spot (zero-coupon) rates |
| Grid | 11 tenors: 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y |
| History | 2004-09-06 to 2026-10-16 (as of 2026-10-18), about 5,700 business days, about 63,000 observations |
| Raw volume | About 260 KB per year of CSV, about 6 MB for the full history |
| Daily cost | One HTTP request |
| Licence | Free reuse including commercial, with attribution "Source: ECB statistics" |

## WHAT is consumed

### The curve

The ECB estimates a zero-coupon yield curve every TARGET business day from euro-denominated, fixed- and zero-coupon bonds issued by euro area central governments rated AAA. It fits a **Svensson** model (continuous compounding, yield error minimisation) and publishes spot, par and instantaneous forward rates for every month from 3 months to 30 years, plus the six model parameters.

YieldLens consumes a narrow slice of that dataset:

| Consumed | Series key (`YC.` + …) | Phase |
|---|---|---|
| Spot rates on the grid | `B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{3M,6M,1Y,2Y,3Y,5Y,7Y,10Y,15Y,20Y,30Y}` | 1 |
| Svensson parameters | `B.U2.EUR.4F.G_N_A.SV_C_YM.{BETA0,BETA1,BETA2,BETA3,TAU1,TAU2}` | 3, with derived curves ([#34](https://github.com/MaxBernstetter/investment-copilot/issues/34)) |

Not consumed, on purpose:

| Not consumed | Why |
|---|---|
| The other 347 monthly spot tenors | The grid is enough for every planned feature; the full set is 30× the volume |
| Par yields (`PY_*`), instantaneous forwards (`IF_*`), spreads (`SRS_*`) | Derivable from spot rates. Processing calculates them ([#40](https://github.com/MaxBernstetter/investment-copilot/issues/40)), so they stay ours to compute and version |
| All-issuer curve (`G_N_C`) | One curve is the phase 1 slice; it is a cheap phase 3 addition |

### Fields per observation

| Field | Example | Meaning |
|---|---|---|
| `KEY` | `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y` | Series identity |
| `DATA_TYPE_FM` | `SR_10Y` | Spot rate, tenor 10Y |
| `TIME_PERIOD` | `2026-10-15` | Valid date (the business day the curve describes) |
| `OBS_VALUE` | `3.390425514` | Yield in percent per annum (`UNIT = PCPA`), continuously compounded |

### Semantics to keep in mind

- **Euro area, not a country.** The AAA curve is a composite of all AAA-rated euro area issuers, and its composition changes over time ("changing composition"). The domain term is **curve**, not country. A country curve (Germany) is a phase 3 source.
- **A model output, not a market quote.** The ECB's values are already fitted. In YieldLens they are *published* values (published by a source), and the source's method (Svensson, the ECB's estimation) is recorded with the source. YieldLens' own *derived* curves are fitted on top of the published grid, and their method versions are ours.
- **Continuous compounding.** Spot rates from other sources (for example US Treasury par yields, semi-annual bond-equivalent) are not directly comparable. Normalization records the compounding convention instead of silently converting ([#19](https://github.com/MaxBernstetter/investment-copilot/issues/19)).
- **No data on closed days.** There is no observation for days that are not TARGET business days. Completeness checks use the TARGET calendar, so these days are not reported as missing.

## HOW it is consumed

### Endpoint

SDMX 2.1 REST API, no key, no registration:

```
GET https://data-api.ecb.europa.eu/service/data/YC/
    B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M+SR_6M+SR_1Y+SR_2Y+SR_3Y+SR_5Y+SR_7Y+SR_10Y+SR_15Y+SR_20Y+SR_30Y
    ?startPeriod=<date>&endPeriod=<date>&format=csvdata&detail=dataonly
```

- `+` joins several series into one request, so the whole grid costs one call.
- `detail=dataonly` drops about 30 attribute columns per row and keeps the raw payload small.
- `format=csvdata` is the simplest format to validate (Pandera on a Polars frame).

### Publication timing

- Observations for valid date *D* are published on the next TARGET business day at about **12:00 CET/CEST**. Measured over 2025–2026, about 80% of dates appear one calendar day later. The rest appear after a weekend or holiday (2–6 days).
- The ECB may delay publication to later the same day or to the next TARGET business day.
- The response's `Last-Modified` header carries the publication time of the latest change.

### Request patterns

| Use | Request | Requests |
|---|---|---|
| Daily load | Grid series, `startPeriod` = *D* − lookback, `endPeriod` = *D* | 1 per day |
| Backfill | Grid series, one calendar year per request, run sequentially | About 23 for the full history |
| Revision check (phase 2) | Grid series, `updatedAfter=<last successful load>` | 1 per day |
| Replay | None. Replay reads stored raw payloads and never calls the source | 0 |

### Responses that need care

| Response | Meaning | Handling |
|---|---|---|
| `200` with rows | Data delivered | Store raw, validate, normalize |
| `200` with an empty body | No observation in the date window (weekend, holiday, before 2004, not yet published); observed with `format=csvdata` on 2026-10-18 | Empty delivery, a successful run with zero rows |
| `404` problem details "No Series was returned for the query" (also documented as "No results found") | The query matches nothing, e.g. nothing updated since `updatedAfter` | Empty delivery, a successful run with zero rows. **Not an error, not retried.** |
| `200` without the expected date | Not yet published (normal before ~12:00, or a delayed publication) | Late-data handling ([#28](https://github.com/MaxBernstetter/investment-copilot/issues/28)), not a failure of the request |
| `304` | Unchanged since `If-Modified-Since` | No-op run |
| `429`, `502`, `503`, `504`, timeout | Throttled or unavailable | Retry with backoff per the access policy |

### Access policy for this source

The generic rules are in [[12-data-pipeline#Source access policy]]. The ECB publishes no rate limit. The API sits behind a web application firewall (MyraCloud) that can block bursty clients, so YieldLens sets a conservative limit itself:

| Setting | Value |
|---|---|
| Concurrent requests | 1 |
| Minimum interval between requests | 2 s |
| Request timeout | 60 s |
| Attempts per request | 3, exponential backoff with jitter, `Retry-After` honoured |
| Identification | `User-Agent: YieldLens/<version> (+https://github.com/MaxBernstetter/investment-copilot)` |
| Conditional requests | `If-Modified-Since` (the API answers `304`) |
| Daily budget | Counted in HTTP attempts, retries included. ≤ 10 in normal operation (one daily request, at most 9 for a failing load); a backfill of the full history adds about 23 when no request is retried, at most 9 per year on retries |

### Revisions and knowledge time

- **Revisions are rare.** Checked with `includeHistory=true`: the 10Y spot series has no revised value in 2025–2026 (455 releases). 2008 shows none either, but has only two releases on record. The corrected-yield demo therefore relies on the scenario mechanism ([#25](https://github.com/MaxBernstetter/investment-copilot/issues/25)). Real revisions are still detected when they happen ([#28](https://github.com/MaxBernstetter/investment-copilot/issues/28)), because `updatedAfter` returns every changed observation regardless of its age.
- **Knowledge time is ours.** `known_from` is the time YieldLens stored the value, also for backfilled history. The ECB's publication time (the `Last-Modified` header, or `validFromDate` from `includeHistory`) is kept as delivery metadata in the raw layer, never used as knowledge time. A backfilled year therefore becomes "known" on the day of the backfill. That is honest, and the time-travel features are demonstrated on data loaded after go-live and on scenarios.
- The ECB's version history only goes back to a bulk load on 2010-11-09. Data before that has no real publication timestamps.

### Terms of use

The [ESCB policy on reuse of statistics](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) allows free reuse, commercial use included, if:

- the source is quoted: "Source: ECB statistics". The API and the UI show it wherever ECB values appear ([#47](https://github.com/MaxBernstetter/investment-copilot/issues/47), [#37](https://github.com/MaxBernstetter/investment-copilot/issues/37)).
- the statistics, including metadata, are not modified. Published values are stored and served exactly as delivered. Anything YieldLens calculates is labelled *derived*, never presented as ECB data.

## WHY this source

The full comparison is in [[0016-ecb-aaa-curve-as-first-source]]. In short:

- **Fits the domain:** a European, AAA government curve built with a standard central-bank method. That is the daily input of a group-level yield-curve platform.
- **Cheapest to run politely:** keyless, free, one request per day, conditional requests and incremental `updatedAfter`.
- **Clear source contract:** a stable SDMX data structure (`ECB_FMD2`) with typed series keys, so schema-drift checks have a precise baseline.
- **Long, clean history:** daily from 2004, with no gaps beyond TARGET holidays.
- **Room for depth:** the published Svensson parameters let processing check its own curve maths against the ECB's in phase 3.

## Follow-up sources (phase 3)

Candidates for [#29](https://github.com/MaxBernstetter/investment-copilot/issues/29), to be verified when that work starts:

| Source | Adds | Watch out for |
|---|---|---|
| Bundesbank, daily term structure of listed Federal securities (SDMX) | A real country curve (Germany); a cross-source check against ECB AAA ([#39](https://github.com/MaxBernstetter/investment-copilot/issues/39)) | Shorter maturity range; Bundesbank terms of use |
| US Treasury, daily par yield curve (CSV/XML) | Second market, history since 1990, par yields (so processing bootstraps zero rates) | Tenors added over time (1.5M and 4M are newer columns): real schema drift. Different compounding convention. |
| ALFRED (St. Louis Fed) | Real vintages for US series | Needs an API key (a secret), and has its own terms of use |
