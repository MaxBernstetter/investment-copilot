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

## Validation beyond tests

Tests prove correctness before release. Transparency proves correctness in operation:

- After deployment, the readiness check passes and the service's dashboard shows expected throughput and no new alerts.
- Business validation: runs, quality results and lineage for the change are visible through the transparency interface.

## Done means

See the [[README#Definition of done|Definition of done]].
