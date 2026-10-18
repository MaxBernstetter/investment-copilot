# Problem Statement

Next: [[01-problem-solution]]

## Problem

Yield curves feed risk calculations, valuation and investment decisions. Downstream users need more than the latest curve. They need to be able to answer:

- **Origin:** Was this value published by a source, or estimated by us?
- **History:** Was it corrected later, and when did we learn about the correction?
- **Reproducibility:** What did we report last Tuesday, and would a rerun today give the same answer?
- **Trust:** Did today's load succeed, or did something fail silently?

## Why current approaches fall short

- Charting and data tools show the latest value and overwrite history.
- Corrections and methodology changes replace old numbers, so past reports can't be reproduced.
- Source and method are not attached to the value, so numbers can't be traced.
- Data-quality problems surface late and without explanation.

## Who is affected

| Persona | Pain |
|---|---|
| Risk expert / portfolio manager | Can't cite or trust a number; can't compare past and present states |
| Data steward / operator | Failures and anomalies are found by accident; recalculations are manual and risky |
| Downstream system | Receives values that change without a trace |
| Quant / analyst | Can't compare curve methodologies or see what a change affected |

## Scope of the problem

Government bond yield curves: daily observations over standard maturities, a few countries, several years of history. The dataset is small. The difficulty is correctness, traceability and reproducibility, not volume.

## Why yield curves

- Yield curves are the core of the target domain (a group-level yield-curve and risk-parameter platform).
- They have a natural time series, standard maturities, source revisions, and a real calculation side (fitting, interpolation, forwards).
- The domain is bounded, so a data engineer can work in it without deep quant knowledge.
- The same problem applies to other risk parameters, so the solution should not hard-code yield curves where avoidable.
