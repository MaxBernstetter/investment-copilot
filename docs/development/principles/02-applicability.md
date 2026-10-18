# Applicability

Before designing anything, check that the piece **applies**: that it solves the real problem, belongs where it is planned, and is needed now.

## Questions before starting

1. **Problem:** which user or system problem does this solve? Is it written in the issue?
2. **Owner:** which bounded context owns this behaviour (`docs/architecture/01-context-map.md`)? If the answer is "several", the cut is wrong.
3. **Need:** is it needed for the current phase, or only "nice to have later"? Later means a new issue, not code now.
4. **Fit:** does an existing service, interface, library or pattern already cover it? Prefer extending what exists.
5. **Evidence:** how will we know it works for the user? This becomes the acceptance criteria (see [[05-testing]]).

## Choosing technology

- Pick a tool because the problem needs it, not because it's available. Every new dependency must be justified in the issue or an ADR.
- Prefer the platform's existing standards: Oracle/PL/SQL, FastAPI, Airflow, OpenTelemetry.
- A significant or hard-to-reverse choice gets an ADR in `docs/architecture/adr/`.

## Cutting the work

- Cut **vertical slices**: a narrow path through every needed layer (schema → service → API → UI → test) that is demoable on its own.
- A slice fits into one issue and one pull request.
- If requirements change during implementation, update the issue first, then the code.

## Red flags

- "We might need this later": defer it.
- "This touches every service": check the boundaries; maybe it belongs in a contract or the platform.
- "No way to test this": the design or the requirement is unclear.
