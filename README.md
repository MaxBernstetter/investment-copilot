# yield-lens

**YieldLens** — an explorable, auditable and historically reproducible government bond yield dataset.

## What is this project about?

### The problem

Yield curves feed risk calculations, valuation and investment decisions. Users need more than the latest curve. They need to know where a value came from, whether it was corrected and when, what was reported last Tuesday, and whether today's load succeeded. Most tools show only the latest value and overwrite history, so past results can't be reproduced and numbers can't be traced.

### The idea

YieldLens is a small platform for government bond yield curves, built on one core dataset in which nothing is overwritten:

- **Bitemporal history:** every value has a valid time (the date it applies to) and a knowledge time (when the platform learned it). Corrections and recalculations add versions.
- **Time travel:** every view and API call accepts an as-of date, so you can ask "what did the platform show last Tuesday, based on what it knew then?"
- **Provenance:** every value links to its source, ingestion run, quality checks and, for calculated curves, its method version.
- **Data quality:** rule results are stored as data, so failed or suspicious loads are visible and explained.
- **Derived curves:** curves fitted and interpolated by the platform, with historical recalculation when the methodology changes.

It consists of a data platform, an API, an explorer UI and an operations view. It covers a few countries, daily observations and several years of history. It is not a trading system.

More detail is in [docs/idea/](docs/idea/):

1. [Problem statement](docs/idea/00-problem-statement.md)
2. [Problem solution](docs/idea/01-problem-solution.md)
3. [Features](docs/idea/02-features.md)

## Architecture

Domain services, interfaces, data model, tech stack and deployment: see [ARCHITECTURE.md](ARCHITECTURE.md).

## Development

### Demo: time travel on the local stack

Prerequisites: Docker, and the devbox shell from this repository. The stack uses local-only default passwords (see `src/deploy/Taskfile.yml`); `task dev:seed` makes live calls to the ECB.

1. `devbox shell`
2. `task dev:up`: starts Oracle, applies the migrations and starts the `persistence` and `access` APIs (`http://localhost:8001`, `http://localhost:8000`).
3. `task dev:seed`: loads ECB history from 2024-01-01 in two steps. The first load stops at a cutoff about 20 business days before yesterday. The second load covers the days after it. The task prints a knowledge time between the two loads and a `?as_of=` URL.
4. `task frontend:dev`, then open <http://localhost:5173>: the latest curve is shown.
5. Pick an older valid date in the explorer. The latest valid date is about 20 business days before yesterday.
6. Open the printed `?as_of=` URL. Only the data the platform knew at that time is shown. Press "Now" to return to the latest view.

The frontend calls `access` at `http://localhost:8000`; set `VITE_ACCESS_URL` to use another address.

Rerunning `task dev:seed` records nothing new: the loads are idempotent. `task dev:down` stops the stack and keeps its data; `task dev:reset` also removes the data.
