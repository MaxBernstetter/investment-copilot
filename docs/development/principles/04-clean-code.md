# Clean Code

Code is read far more often than it is written. Optimize for the reader.

## Naming and language

- Use the **ubiquitous language** of the context (`docs/architecture/01-context-map.md`): `observation`, `version`, `as_of`, `method_version`. Don't use synonyms.
- Names say what something is or does; no abbreviations except established ones (`id`, `url`).
- Booleans read as questions (`is_simulated`, `has_open_version`).

## Functions and modules

- **Small and focused:** one level of abstraction per function. If you need "and" to describe it, split it.
- **Few parameters:** group related values into a value object instead of passing many.
- **No hidden side effects:** a function named `get_…` doesn't write.
- **Pure domain:** domain code has no I/O; I/O lives in adapters (hexagonal layout, see `docs/architecture/06-repository-layout.md`).
- **Dependencies injected:** pass collaborators in; don't construct them inside use cases.

## SOLID, applied pragmatically

- **Single responsibility:** one reason to change per module.
- **Open/closed:** new quality rules or source adapters are added as new implementations of an existing interface, not by editing a switch statement.
- **Liskov:** every adapter honours the full interface contract, including errors.
- **Interface segregation:** ports are small and specific to the use case.
- **Dependency inversion:** application code depends on ports, not on Oracle or HTTP.

## Errors

- Fail fast and explicitly: validate at the boundary (contracts, config) and trust data inside.
- Domain errors are typed exceptions mapped to RFC 9457 problem responses at the edge.
- Never swallow errors. Log once at the boundary with context, then re-raise or handle.

## Comments and formatting

- Code explains *what*; comments explain *why* (decisions, domain rules, non-obvious constraints).
- Formatting, linting and type checks are automatic (see [[#Tooling]]); style is not debated in reviews.

## Tooling

- **Python:** ruff (lint + format), mypy strict, full type hints, no implicit `Any` at interfaces.
- **Frontend:** TypeScript strict, ESLint, generated API client (no hand-written request types).
- **C++:** C++20, clang-format, built via scikit-build-core, exposed only through the pybind11 module.

## Boy-scout rule

Leave touched code a little cleaner than you found it, but keep refactors in scope. Larger clean-ups get their own issue.
