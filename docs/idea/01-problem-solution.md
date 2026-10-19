# Problem Solution: YieldLens

Previous: [[00-problem-statement]] · Next: [[02-features]]

## Idea

**YieldLens** turns government bond yield data into an explorable, auditable and historically reproducible dataset. It is a miniature of a group-level yield-curve and risk-parameter platform.

## What we are building

A platform with four faces on one core dataset:

| Face | Purpose |
|---|---|
| Data platform | Ingests, historizes, validates and serves curve data |
| API | Machine access for downstream consumers, always with an "as-of" option |
| Explorer UI | Human exploration of curves, history, quality and lineage |
| Operations view | Pipeline runs, failures, backfills, quality results |

An optional insight layer (ML/AI) comes last.

## Core concepts

- **Published curve:** values taken as delivered by a public source.
- **Derived curve:** a curve YieldLens calculates (fit, interpolate, forwards). It records the method and method version.
- **Bitemporal:** every value has a *valid time* (the date it applies to) and a *knowledge time* (when the platform learned it). Nothing is overwritten. Corrections and recalculations add versions.
- **Lineage:** every value links to its source, ingestion run, quality checks and, if derived, its inputs and method version.

## Key scenario: the corrected yield

A provider publishes a 10-year yield, then corrects it two days later. YieldLens keeps both versions and shows when each became known, the source and reason, whether a quality check caught it, and which derived values changed.

A user can ask: *"What did the platform show last Tuesday, based on what it knew then?"* and get exactly that, in the UI and via the API.

Public sources rarely revise values. A clearly labelled **scenario mechanism** injects corrections, late data, missing days and bad values for demonstration and tests. It is never mixed with real source data.

## Data scope

- A few countries (e.g. Germany/euro area, USA, one or two more) from free public sources
- Daily observations, maturities of roughly 3 months to 30 years, several years of history
- Plus versions, derived curves, quality results and run history
- Well below 1 GB

## Non-goals

- Trading, portfolio management, order execution
- Real-time or intraday data
- Complex derivative pricing (quant depth stops at fitting, interpolation and forwards)
- User management beyond what the demo needs

## Phasing

1. **Foundation:** one published curve, bitemporal storage, ingestion, basic explorer, as-of query
2. **Trust:** quality rules, provenance view, scenario mechanism, corrections demo, API
3. **Depth:** more countries, derived curves, methodology versions, historical recalculation, impact view, data marts
4. **Insight:** anomaly detection, grounded natural-language explanations

Each phase is demoable on its own.

## Success criteria

- The corrected-yield scenario runs end to end, including an exact reproduction of a past view
- A methodology change recalculates years of history without losing previous results
- A failed or bad load is detected and explained without reading logs
- Every number in the UI or API traces to a source or method version
- A new reader can understand the project from `docs/` alone

## Fit to the target role

The project is shaped so each major requirement of the target role is exercised by a real feature (details per domain in [[02-features]]).

| Role requirement | Where it shows |
|---|---|
| Bitemporal historization, data modelling, SQL/PL-SQL | Versioned core dataset, as-of access |
| ETL, market-data integration, data marts | Multi-source ingestion, curve/spread/quality marts |
| Data quality framework | Stored rule results and statuses |
| REST APIs | Versioned API with as-of and lineage metadata |
| Airflow / orchestration, operations | Scheduled loads, backfills, recalculation jobs, runbook |
| Python application with UI | Python backend services; explorer and operations views (SPA) |
| Historical recalculation | Methodology change produces versioned series |
| Quant stack (QuantLib, C++) | Derived curves |
| CI/CD, Git, Docker, Linux, testing, docs | First-class deliverables |
| ML / AI / automation | Insight layer |

Open: Oracle/PL-SQL availability for a personal project and German-language content are stack and scope decisions for later.

## Open questions

- ~~Which countries and sources offer the best reliability, history and genuine revisions?~~ Answered for phase 1 in [[01-data-sources]] and [[0016-ecb-aaa-curve-as-first-source]].
- Which derived-curve methods are worth including before scope grows?
- How prominent should the insight layer be?
- ~~Keep the name YieldLens, or rename (the repo was `investment-copilot`)?~~ Kept: the product is YieldLens, the repository and project board are `yield-lens`.
