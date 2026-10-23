# AGENTS.md

## Project documentation
- `docs/` is the Obsidian vault. Entry points: `ARCHITECTURE.md`, `docs/architecture/README.md`, `docs/development/README.md`.
- Keep documentation consistent with the implementation.
- Frontend work follows `docs/development/design-guidelines.md` (Direction A). The `designer` agent writes the text spec of a UI issue against it before planning. Frontend changes are validated by code only (unit tests, e2e behaviour and axe). Nothing reads or compares screenshots; the user reviews the look.

## Before planning or implementing
1. Read `docs/development/principles/README.md` (workflow and Definition of done).
2. Read the principle notes the task touches:
   - always: `02-applicability`, `03-simplicity`
   - writing code: `04-clean-code`
   - adding or changing behaviour: `05-testing`
   - services, data or pipelines: `01-twelve-factor`, `06-scalability`
   - CI, deployment, secrets: `07-delivery-and-security`
3. For tracked work, follow `docs/development/01-task-management.md`.
4. In every plan, name the principles that apply and how the plan meets them.

Trivial changes (typos, docs wording) skip steps 2 and 4.

## Project board
- The board <https://github.com/users/MaxBernstetter/projects/2> must reflect the current state of agentic development at all times.
- Set an issue to `In progress` directly when work on it starts, before planning or coding, and update its status on every later change (`In review` once its merge request is open, back to `In progress` when it is reworked).

## GitLab issues
- When opening a merge request for a GitLab issue, prefix the MR title with the issue ID from the issue title, e.g. `[00.10] Load published curve for one country`.
- After opening the merge request, do not wait for CodeRabbit or CI. The orchestrator assesses the CodeRabbit threads (use the `mr-threads` skill) and checks CI before merging.

## Merge request size
Every merge request must be reviewable by a human in one sitting.
- Aim for at most ~400 changed lines, not counting lockfiles and generated files. Treat ~800 as a hard limit.
- One concern per merge request. Do not mix refactoring, formatting or dependency bumps with behaviour changes.
- Check the expected size while planning. If an issue will exceed the limit, propose splitting it into smaller issues or stacked merge requests before implementing, each one independently green and reviewable.
- Do not add scope found during implementation; propose a follow-up issue instead.
- In the description, state what changed and why, and point to where to start reviewing.

## Worktrees
Issue, merge request and worktree relate 1:1:1. An issue split into stacked merge requests gets one worktree per merge request.
- Work on one merge request only in its own git worktree under `.claude/worktrees/`, on its own branch. Never let two merge requests, issues or agents share a worktree, and never edit a worktree you did not create.
- Name the worktree after its branch, e.g. `.claude/worktrees/feat-19-1-grid-reference` for `feat/19-1-grid-reference`.
- Before creating a worktree or starting an agent, check that no other session or agent already owns the issue (`ListAgents`, the board, existing worktrees). If one does, ask it instead of starting in parallel.
- Remove the worktree (`git worktree remove`) once its branch is pushed and work stops: merge request in review, merged, closed, superseded or paused. The pushed branch is the durable state; to rework, create a fresh worktree from it. Never remove a worktree with uncommitted changes without saving them first.

## Subagents and models
Agentic work is split by model to save tokens (`docs/development/03-agent-harness.md`):
- Grooming, planning, validation and UI specs run on Sonnet 5.5 at low effort: `groomer`, `planner`, `validator`, `designer`.
- All execution runs on Haiku: implementation, exploration and chores such as rebases, checks, board and PR bookkeeping go to `worker`.
- The main session orchestrates and delegates. Keep it from reading or editing code itself beyond what a decision needs.
- Hand `worker` concrete work units from a plan, never open design questions. A `validator` failure goes back to `worker` as its next work unit.
- Skip the harness for trivial changes.
- **No duplicate checks.** The worker runs lint, typecheck, unit tests and build for the services it changed. It runs integration tests only when the change touches migrations, SQL/PL-SQL, or persistence and adapter code that the integration tests cover. It runs e2e only when the change touches `src/frontend/e2e/**` or the e2e config. CI runs everything and gates every merge. A red CI goes back to a `worker` as its next work unit.
- **Validator reviews, CI tests.** The validator reviews the diff against the plan, the acceptance criteria and the Definition of done. It reads the PR's CI result (`gh pr checks`) instead of rerunning the suites. It may run a single targeted test to confirm a suspicion.
- **Skip the validator** for docs-only and config-only changes, pure rebases, review-comment fixes, and changes under about 100 lines with no behaviour change. Those merge on green CI.
- **Acceptance checklist in every brief.** The orchestrator puts the issue's acceptance criteria (or the plan's, for that merge request) in the worker brief as a checklist. The worker ticks each item off in its report before pushing, and stops instead of guessing when one cannot be met.
- **No stacked merge requests on unmerged branches by default.** Start the next merge request of an issue once the previous one has merged, and run other independent work in parallel meanwhile. Stack only when blocking would idle all work, and then rebase onto main right after the base merges, since rebases rewrite commits.
- **Quiet output.** Workers and validators run tests quietly (`pytest -q`, Playwright's `--reporter=line`, vitest's default) and read only the tail or the failures, for example `… 2>&1 | tail -n 40`. Never read full logs into context.
- **Planner only for multi-MR issues.** S-size issues (one merge request) skip the planner. The orchestrator briefs the worker from the groomed acceptance criteria.
- **Agents do not wait or poll** for CodeRabbit or CI. The orchestrator checks the CodeRabbit threads and CI before merging.
- **Orchestrator session hygiene.** Start a fresh main session per batch of work, since state lives on the board, in PRs and in memory. Stop finished agents. Use one merge run per batch. See `docs/development/03-agent-harness.md`.

## Agent skills
- Shared project skills are stored in `.agents/skills/`.
- Before implementing a task, check for relevant skills and follow their instructions when applicable.
- Read the relevant skill's `SKILL.md` before applying it.
- Prefer existing skills over duplicating workflows in project instructions.
- Do not invoke unrelated skills or force specialized workflows onto trivial changes.

## Before finishing
- Go through the Definition of done in `docs/development/principles/README.md` and report each item as met, not applicable, or open.
- Make the smallest correct change, run the relevant tests and checks, and review the diff.
- Update documentation when behaviour, architecture or workflows change.
