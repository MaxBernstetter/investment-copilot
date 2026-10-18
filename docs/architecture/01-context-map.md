# Context Map

Each domain from [[02-features]] is a bounded context implemented as a service. A context owns its model, its language, its data and its code. Transparency is a capability of every context, not a context of its own (see [[0008-transparency-per-service]]).

## Contexts

| Context | Service | Owns | Does not own |
|---|---|---|---|
| Data Ingestion | `ingestion` | Source registry and calendars, source payload schemas, raw payloads, normalization rules (versioned), quarantine of bad deliveries, scenario definitions, source runs and delivery alerts | Stored values and their history |
| Data Persistence | `persistence` | Bitemporal observations (published and derived), versions, curve definitions and maturity grid, value metadata and lineage, knowledge-state diffs | Quality rules, calculations |
| Data Processing | `processing` | Quality rules (with severity) and results, validation gates, market calendars and conventions, calculation methods and versions, recalculation impact, marts, anomaly findings | Raw data, value history |
| Data Access | `access` | Public API contract, cross-service lineage assembly, response caching | Any persisted data |
| User Frontend | `frontend` | UI state | Any data |

## Relationships

```
ingestion ──(customer/supplier)──▶ persistence ◀──(partnership)──▶ processing
                                        │                               │
ingestion, persistence, processing ──(upstream)──▶ access (open host service) ──▶ frontend

all services ──(conformist)──▶ transparency contract + observability platform
```

- **ingestion → persistence (customer/supplier):** persistence defines the write interface for observations; ingestion conforms to it.
- **processing ↔ persistence (partnership):** processing reads observations as of a knowledge time and writes derived observations back. Both interfaces evolve together.
- **access (open host service):**
  - It is the single published language for external consumers and the frontend.
  - It translates internal models into the public contract and acts as an anti-corruption layer.
  - It assembles cross-service lineage by following upstream refs.
- **transparency (shared contract):** every service conforms to the common transparency interface and the platform telemetry conventions (see [[10-observability]]).
- **orchestration and observability:** platform components, not contexts. They hold no domain logic.

## Ubiquitous language (core terms)

- **Observation:** a yield for a curve, maturity and valid date.
- **Version:** one known state of an observation, with its knowledge interval.
- **Valid time:** the business date an observation applies to.
- **Knowledge time:** when the platform learned a version.
- **As-of:** a query at a given knowledge time.
- **Published / derived:** whether a value came from a source or from a method.
- **Method version:** an identified, immutable revision of a calculation method.
- **Run:** one execution of a step within a service.
- **Lineage:** the links from a value to its source, run, checks and inputs.
- **Alert:** a condition a service flags as wrong; business (domain meaning) or system (technical health).
