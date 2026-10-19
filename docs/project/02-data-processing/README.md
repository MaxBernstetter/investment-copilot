# 02 Data processing

Data processing checks and derives data on top of the published values in persistence: completeness and plausibility checks with a quality status per value (phase 2), and later derived measures and fitted curves (phase 3). The processing service reads observations only through the persistence API and keeps its results in its own schema; the service itself follows with [#137](https://github.com/MaxBernstetter/yield-lens/issues/137).

## Notes

- [[01-plausibility-thresholds]]: the range and jump rules of the plausibility checks, how their thresholds were derived from the full ECB history, and how to re-derive them
