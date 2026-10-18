# ADR 0015: pre-commit framework for git hooks

**Status:** Accepted · 2026-10-18

## Context
Basic hygiene (formatting, secrets, syntax) should be caught before a commit, in every language of the monorepo, with versions pinned and identical for everyone.

## Decision
- Use the **pre-commit** framework (`.pre-commit-config.yaml`), with pinned hook versions.
- Hooks are fast and file-scoped: general hygiene, gitleaks, ShellCheck, shfmt and actionlint. Language hooks are added as components appear.
- Slow checks (type checks, tests) stay in tasks and CI.
- CI runs all hooks on all files as a required check.

## Consequences
- Language-agnostic, with each hook in an isolated, cached environment; works without Node.
- Hooks must stay fast, or developers will skip them; CI is the safety net.

Rejected: Husky + lint-staged. Node-centric, and a poor fit for a Python/Bash/SQL-heavy repo.
