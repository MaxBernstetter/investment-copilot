# Testing

A piece of software is working when its **acceptance criteria are proven by automated tests** and its **behaviour is observable in operation**.

## Start from the acceptance criteria

1. Turn each acceptance criterion of the issue into at least one test before or while implementing.
2. If a criterion can't be tested, clarify it in the issue first.
3. Test behaviour through the public interface of the module, not its internals.

## Test pyramid

| Level | Proves | Tooling | Speed | Share |
|---|---|---|---|---|
| Unit | Domain logic and use cases are correct (no I/O) | pytest, Vitest | ms | Most tests |
| PL/SQL | Packages enforce versioning and as-of rules | utPLSQL | s | All packages |
| Integration | Adapters work against real Oracle and HTTP | Testcontainers | s | Each adapter |
| Contract | The service matches its OpenAPI; consumers' expectations hold | Schemathesis / contract tests | s | Every interface |
| End-to-end | The key scenario works across the stack (corrected yield, as-of reproduction) | Compose stack in CI | min | Few |

## Domain-specific test rules

- **Bitemporal correctness:** every change to the persistence logic includes as-of tests: before the correction, after the correction, and the open version.
- **Idempotency:** every write operation has a test showing that running it twice gives the same result.
- **Reference implementations:** numerical code (curves, forwards, the C++ kernel) is tested against a known reference implementation or published values, with explicit tolerances.
- **Deterministic data:** tests use fixed fixtures and fixed knowledge times. No dependency on today's date or live sources.
- **Bugs:** a fix starts with a failing test that reproduces the bug.

## Test strategy in YieldLens

Each level lives next to the code it proves. The table says where it is, and whether it runs locally, in CI, or both.

| Level | Where | Local | CI |
|---|---|---|---|
| Unit | `src/services/<name>/tests/unit`, `src/frontend` (Vitest), `src/contracts` | `task <component>:test:unit` | Every pull request (required checks) |
| PL/SQL | utPLSQL suites under `src/services/persistence` and `src/services/ingestion` (`ING`) | `task persistence:test:integration`, `task ingestion:test:integration` (Docker needed) | Integration jobs of `persistence.yml` and `ingestion.yml` |
| Integration | `tests/integration` of the services; Oracle Free and HTTP through Testcontainers | Same tasks as PL/SQL (Docker needed) | Integration jobs (required checks) |
| Contract | OpenAPI drift checks in the access and processing unit tests (`src/contracts/openapi/access/v1.json` and `src/contracts/openapi/processing/v1.json` must match the app; the processing check runs in `task processing:test:unit`); contracts unit tests | `task access:test:unit`, `task processing:test:unit`, `task contracts:test:unit` | Every pull request |
| End-to-end | `src/e2e`: the corrected-yield scenario through the access api | `task dev:reset`, `task dev:up`, `task dev:e2e` (Docker needed) | `e2e.yml` (required check) |

Locally, unit tests need no Docker and run in seconds; integration and end-to-end tests need the Docker stack. Everything in CI is reproducible with the same `devbox run -- task ...` command.

### The corrected-yield end-to-end test

`src/e2e/tests/test_corrected_yield.py` runs the `corrected-yield` scenario ([[05-scenarios]]) on the simulated curve `ecb-aaa-spot-sim` and reads the result back through the access api. It proves the cycle a user sees: a gap, a bad value, a late value and a correction. It also proves the reproducibility rule:

- **Reproducibility:** an `as_of` answer is byte-identical with the same `ETag` after any later write. Once a past view is taken, a correction must not change it, and a conditional request with that `ETag` gets `304`.
- **Current view:** after the correction, the latest answer shows the corrected value, and the version history of the value lists `initial` then `correction`, all with `source_id = scenario`.
- **Isolation:** the scenario never writes to the real curve `ecb-aaa-spot`.

The test is CI-only in the required-check sense: it runs on every pull request and on pushes to `main`, and it needs a fresh stack, so it always starts from `task dev:reset`.

### Scenarios as test data

Scenarios are the source of test data for end-to-end tests. They write a simulated curve in steps, with fixed valid dates and fixed values, through the same write interface as real data. Tests therefore need no live source and no dependency on today's date, and they never touch a real curve. A test that needs a specific shape of data (a gap, a correction) adds a scenario event rather than a hand-written fixture.

### Quality gates

Quality gates are warn-only in phase 2: a gate that fails is reported but does not block a merge. A gate becomes blocking only when it is added to the required checks.

## Validation beyond tests

Tests prove correctness before release. Transparency proves correctness in operation:

- After deployment, the readiness check passes and the service's dashboard shows expected throughput and no new alerts.
- Business validation: runs, quality results and lineage for the change are visible through the transparency interface.

## Done means

See the [[README#Definition of done|Definition of done]].
