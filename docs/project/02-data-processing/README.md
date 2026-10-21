# 02 Data processing

Data processing checks and derives data on top of the published values in persistence: completeness and plausibility checks with a quality status per value (phase 2), and later derived measures and fitted curves (phase 3). The processing service reads observations only through the persistence API and keeps its results in its own schema. Its skeleton is in place ([#137](https://github.com/MaxBernstetter/yield-lens/issues/137)); the checks follow.

## Notes

- [[02-processing-service]]: the service skeleton: layers, process types, configuration and tasks
- [[01-plausibility-thresholds]]: the range and jump rules of the plausibility checks, how their thresholds were derived from the full ECB history, and how to re-derive them
- [[03-quality-checks]]: the quality rules, their severities and statuses
- [[04-derived-measures]]: spreads, slope, curvature and inversion: definitions, missing and flagged inputs, method version
