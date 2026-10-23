# Agent Harness

Agentic development splits work by model to keep token use down. **Sonnet 5.5** at low effort is used where judgement matters: grooming, planning and validating. **Haiku 5.5** is the workhorse and does everything else. The main session orchestrates: it delegates, passes results on, and talks to the user. It does not do the work itself.

## Agents

The project subagents live in `.claude/agents/` and are committed to the repository.

| Agent | Model | Tools | Job |
|---|---|---|---|
| `groomer` | Sonnet 5.5 (low) | no file edits | Gets issues to Ready: acceptance criteria, dependencies, size, splits ([[01-task-management]]) |
| `planner` | Sonnet 5.5 (low) | read-only | Turns one issue into merge-request-sized slices and concrete work units |
| `worker` | Haiku 5.5 | all but spawning agents | Implements one work unit, or does one chore: rebase, checks, board and PR bookkeeping, broad search |
| `validator` | Sonnet 5.5 (low) | read-only, reads CI results | Checks a change against plan, acceptance criteria and the [[principles/README#Definition of done\|Definition of done]]; pass or fail |
| `designer` | Sonnet 5.5 (low) | read-only | Writes the text spec of a UI issue before planning (components, props, copy, states, tokens, a11y) against [[design-guidelines]] |

## Flow

```mermaid
flowchart LR
  G[groomer<br/>Sonnet] -- S-size issue --> W[worker<br/>Haiku]
  G -- multi-MR issue --> P[planner<br/>Sonnet] --> W
  W -- docs, config, rebase, small --> PR[pull request]
  W -- other changes --> V[validator<br/>Sonnet]
  V -- fail: fix list --> W
  V -- pass --> PR
  PR --> CI[CI gates merge]
  CI -- red --> W
```

1. **Groom** the issue if it is not Ready yet.
2. **Plan** multi-MR issues only. The plan holds every design decision, so the worker does not have to make any. A UI issue gets a `designer` spec before planning, so the plan takes its components, states, copy, tokens and accessibility needs from that spec. An S-size issue (one merge request) skips the planner: the orchestrator briefs the worker from the groomed acceptance criteria.
3. **Work**: one `worker` per work unit, each in the worktree of its merge request (see `AGENTS.md`, Worktrees). Each brief carries the acceptance criteria as a checklist. The worker ticks each item off before pushing, and stops if one cannot be met. The worker runs the checks for what it changed (see `AGENTS.md`, No duplicate checks). Independent units can run in parallel.
4. **Validate** the change, unless it is docs-only, config-only, a pure rebase, a review-comment fix, or under about 100 lines with no behaviour change. Those merge on green CI. The validator reviews the diff against the plan, the acceptance criteria and the Definition of done, and reads `gh pr checks`. On a failure, the fix list goes back to a `worker` as the next work unit. The validator checks frontend changes by code: unit tests, e2e behaviour and axe. No agent reads, renders or compares screenshots, and there is no visual review step. The user reviews the look.
5. **Open** the pull request. CI runs everything and gates the merge. A red CI goes back to a `worker` as the next work unit.
6. **Merge** after the orchestrator has assessed the CodeRabbit threads and CI. Agents do not wait or poll for either.
7. **Next**: start the next merge request of an issue once the previous one has merged. Run other independent work in parallel meanwhile. Stack merge requests only when blocking would idle all work, and then rebase onto main right after the base merges.
8. Mechanical steps also go to a `worker`: push, open the pull request, update the board, rebase stacks.

Trivial changes (typos, a one-line fix) skip the harness.

## Orchestrator session hygiene

- Start a fresh main session per batch of work. State lives on the board, in pull requests and in memory, not in the session.
- Stop finished agents, so they do not hold context or keep running.
- Use one merge run per batch, rather than one per pull request.

## Why this split

- Most tokens go into reading files, running commands and writing code. A cheaper model does that well once the decisions are made.
- Sonnet only reads what it needs to judge, and returns a short result: a plan, a verdict or proposed issue text.
- The main session's context stays small, because subagents return summaries instead of file contents and logs.

## Built-in subagents

Built-in agents such as `Explore` and `general-purpose` inherit the main session's model, unless a default subagent model is configured. To make Haiku the default for them, set this in your local `.claude/settings.local.json`. It is a personal setting and is not committed.

```json
{ "env": { "CLAUDE_CODE_SUBAGENT_MODEL": "claude-haiku-5-5" } }
```

The agents in `.claude/agents/` pin their own model and are not affected by it.

Related: [[01-task-management]], [[principles/README|principles]], [[design-guidelines]]
