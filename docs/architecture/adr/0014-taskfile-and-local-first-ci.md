# ADR 0014: Taskfile tasks and local-first CI

**Status:** Accepted · 2026-10-18

## Context
A polyglot monorepo (Python services, PL/SQL, C++, TypeScript, Airflow) needs one consistent way to run tasks. Logic hidden in CI YAML can't be run or tested locally, and drifts from what developers do.

## Decision
- **go-task** (`Taskfile.yml`) is the single entry point for every task. The root Taskfile includes per-component Taskfiles with a standard set of task names.
- **Taskfiles only glue:** each command is a single binary or script call. Logic lives in Bash scripts under `src/scripts/`, which are linted (ShellCheck, shfmt) and tested (bats).
- **devbox** pins the whole toolchain for local use and CI.
- **CI workflows are thin:** provision devbox, then call tasks. Every CI step can be reproduced locally with the same command.

## Consequences
- One way to run anything, for humans, agents and CI; onboarding is `task --list`.
- CI failures are reproducible locally; workflow YAML stays small and rarely changes.
- Discipline needed: no shortcuts with inline shell in Taskfiles or workflows.
- Extra tools to learn (go-task, devbox, bats), all pinned.

Rejected:
- Makefiles. Weak for cross-platform use and arguments, and tempt inline shell.
- Logic in GitHub Actions YAML. Not runnable locally.
