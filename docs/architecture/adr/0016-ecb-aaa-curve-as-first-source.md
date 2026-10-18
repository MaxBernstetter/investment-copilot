# ADR 0016: ECB euro area AAA spot curve as the first source

**Status:** Accepted · 2026-10-18

## Context
Phase 1 loads one published curve from one public source. The source shapes the source contract, the request pattern, the normalization rules and what the time-travel demo can show. Requirements: free and legal to reuse, long daily history, maturities from about 3 months to 30 years, a stable machine interface, cheap to call politely, and relevant to a European yield-curve platform.

## Options

| Option | For | Against |
|---|---|---|
| **ECB Data Portal, euro area AAA curve** | Daily since 2004; 3M–30Y; spot, par, forward and Svensson parameters; keyless SDMX API with `updatedAfter` and conditional requests; free reuse with attribution; European central-bank method | A composite euro area curve, not a country; already model-fitted values; revisions are rare |
| US Treasury par yield curve | Daily since 1990; public domain; par yields give processing real bootstrapping work; tenors added over time (real schema drift) | US market; no model parameters; CSV/XML download instead of a query API |
| Bundesbank term structure (Germany) | A real country curve; Svensson parameters; SDMX API | Shorter maturity range; less central to a euro area platform than the ECB curve |
| ALFRED (St. Louis Fed) vintages | Real vintages, so backfilled history could be bitemporal | Needs an API key; US only; vintages of daily yields rarely differ |

## Decision
- Phase 1 consumes the **ECB euro area AAA Svensson spot curve** on an 11-tenor grid (3M–30Y), as described in [[01-data-sources]].
- Only spot rates on the grid are consumed. Par and forward rates are calculated by processing. Svensson parameters are added in phase 3, together with derived curves.
- **Knowledge time stays ours:** `known_from` is when YieldLens stored a value. The source's publication time is kept as delivery metadata in the raw layer.
- The source is accessed under the [[12-data-pipeline#Source access policy|source access policy]]: rate limited, identified, retried only on transient errors, never called from CI.
- Bundesbank and US Treasury are the phase 3 candidates.

## Consequences
- The domain term is *curve*, not *country*: the first curve is a euro area composite.
- Values are stored and served exactly as delivered, with "Source: ECB statistics" attribution. YieldLens' own calculations are labelled *derived*.
- Real revisions will be rare, so the corrected-yield demo relies on the scenario mechanism. Revision detection still runs against the real source.
- Backfilled history becomes known on the day of the backfill, so time-travel demos use data loaded after go-live and scenarios.
- Real schema drift is unlikely from this SDMX source. Drift detection gets its real test case with the US Treasury source in phase 3.
