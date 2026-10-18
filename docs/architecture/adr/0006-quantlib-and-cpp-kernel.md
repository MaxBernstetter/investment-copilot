# ADR 0006: QuantLib plus a C++ kernel via pybind11

**Status:** Accepted · 2026-10-18

## Context
`processing` fits and interpolates curves, computes forwards, and recalculates long histories. The target role values QuantLib, C++ and Python/C++ integration.

## Decision
- Use **QuantLib (Python bindings)** for established curve methods.
- Implement performance-critical batch routines (e.g. vectorized interpolation/forwards over long histories) as a small **C++20 kernel** exposed via **pybind11**, built with scikit-build-core.
- Every method has an explicit, immutable method version.

## Consequences
- Proven quant methods, plus a demonstrable Python/C++ integration pattern.
- The C++ kernel is optional for correctness: a pure-Python reference implementation is kept and used to test the kernel.
- Requires multi-arch native builds in CI.
