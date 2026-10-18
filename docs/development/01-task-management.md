# Task Management Workflow

## Overview

GitHub Issues and GitHub Projects are the source of truth for project task tracking.

- **GitHub Issues** define bugs, features, improvements, and technical debt.
- **GitHub Projects** provide a consolidated view of tasks, priorities, and workflow status.
- **Pull requests** connect implementation changes to their corresponding issues.
- **Obsidian documentation** under `docs/` captures durable technical knowledge, architecture, and operational procedures.

Tasks should be traceable from initial requirements through implementation, verification, and completion.

## GitHub Project

The board is the user-owned project **Investment-Copilot**: <https://github.com/users/MaxBernstetter/projects/2> (owner `MaxBernstetter`, project number `2`). All epics and tasks of this repository are tracked there.

### Fields

| Field | Values | Use |
|---|---|---|
| Status | Backlog, Ready, In progress, In review, Done | Workflow state, see [[#2. Prioritize and prepare work]] |
| Priority | P0, P1, P2 | P0 = blocking or most urgent, P2 = can wait |
| Size | XS, S, M, L, XL | Relative effort of a task |
| Estimate | number | Optional effort estimate |
| Start date / Target date | date | Planning for the Roadmap view |

Built-in fields such as Assignees, Labels, Linked pull requests, Parent issue, and Sub-issues progress are populated from the issues themselves.

### Views

| View | Layout | Purpose |
|---|---|---|
| Backlog | Board | Items grouped by Status |
| Priority board | Board | Items grouped by Priority |
| Team items | Table | All items with planning fields |
| Roadmap | Roadmap | Timeline by Start date / Target date |
| My items | Table | Items assigned to the current user (`assignee:@me`) |

## Workflow

### 1. Create an issue

Create a GitHub issue for each meaningful bug, feature, or improvement.

Each issue should describe:

- **Problem:** What needs to change and why?
- **Expected outcome:** What should be true when the work is complete?
- **Acceptance criteria:** How will completion be verified?
- **Documentation impact:** Which notes under `docs/` need to be created or updated?

Keep issues focused and small enough to implement and review independently.

Use labels to classify work, for example:

- `bug`
- `enhancement`
- `documentation`
- `technical-debt`

### Hierarchy and labels

Work is organized as **epics** and **tasks**:

- **Epic:** one issue per domain, labelled `epic`. The domains follow [[02-features]]: `00` Data Ingestion, `01` Data Persistence, `02` Data Processing, `03` Observability (cross-cutting), `04` Data Access, `05` User Frontend, and `06` Engineering Foundation (cross-cutting).
- **Task:** a native sub-issue of its epic, labelled with its domain (e.g. `domain:00-ingestion`).
- **Phase:** each task has a phase label (`phase:1-foundation`, `phase:2-trust`, `phase:3-depth`, `phase:4-insight`).
- **Type:** each task has a type label (`enhancement`, `documentation`, ...).
- **Dependencies:** each task lists the issues that block it in a `## Blocked by` section of its body.

Title convention: `[EPIC-00] Data Ingestion` for epics, `[00.2] Load published curve for one country` for tasks.

GitHub operations by agents go through the GitHub MCP server, see [[02-github-mcp]].

### 2. Prioritize and prepare work

Add issues to the [[#GitHub Project]] and set **Status**, **Priority**, and **Size**.

| Status | Meaning |
|---|---|
| Backlog | Captured but not yet prioritized or ready |
| Ready | Prioritized, sufficiently specified, and ready to implement |
| In progress | Implementation is underway |
| In review | A pull request is awaiting review or verification |
| Done | Changes are merged and required checks have passed |

Before starting substantial work, ensure the issue has clear acceptance criteria and known dependencies.

### 3. Implement the issue

Before coding:

1. Read the relevant issue and its acceptance criteria.
2. Inspect the existing implementation, tests, and relevant documentation.
3. Check `AGENTS.md` and any applicable project skills.
4. Identify the smallest implementation that satisfies the requirements.
5. Assign the current user to the task and move its project item to `In progress`.

During implementation:

- Keep changes scoped to the issue.
- Add or update tests where appropriate.
- Update relevant Obsidian notes under `docs/` when behavior, architecture, configuration, or workflows change.
- Record significant architectural decisions in the appropriate Architecture Decision Record (ADR).

If the requirements change materially, update the issue before expanding the implementation.

### 4. Open a pull request

Create a pull request that references the issue, for example:

`Closes #42`

The pull request should include:

- A concise summary of the change.
- The issue being addressed.
- Tests and verification performed.
- Documentation changes, if applicable.
- Known limitations or follow-up work.

Move the task to `In review` while review and required checks are pending.

### 5. Verify and close

Before considering the task complete, check the [[principles/README#Definition of done|Definition of done]] and address review feedback.

Merge the pull request when the required checks and reviews pass. GitHub can automatically close the linked issue when a pull request containing a supported closing keyword is merged into the repository's default branch.

Move the project item to `Done` once the completion criteria are satisfied.

## AI Agent Responsibilities

Coding agents must:

- Use GitHub Issues as the source of truth for tracked work.
- Read the relevant issue before implementing substantial changes.
- Ask for clarification or identify unresolved requirements rather than inventing acceptance criteria.
- Avoid silently expanding the scope of an issue.
- Update tests and documentation when appropriate.
- Report verification results accurately.
- Never claim to have created, updated, assigned, or closed an issue unless the action actually succeeded.

Agents may propose new issues for discovered bugs, technical debt, or follow-up improvements. Keep unrelated work separate from the current task.

## Documentation Boundaries

Use each system for its intended purpose:

- **GitHub Issues:** Requirements, acceptance criteria, task discussions, and follow-up work.
- **GitHub Projects:** Priorities, ownership, status, and planning.
- **Pull requests:** Implementation review, verification, and change history.
- **`docs/`:** Durable project knowledge, architecture, decisions, development instructions, and operational guidance.

Do not duplicate the entire issue tracker in Markdown files. Link to GitHub issues when referencing tracked work from documentation.

## Guiding Principle

Every substantial change should have a clear purpose, verifiable completion criteria, appropriate tests, and up-to-date documentation. Keep the workflow lightweight for trivial changes and apply the full process to work that warrants it.
