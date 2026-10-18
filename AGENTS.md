# AGENTS.md

## Project documentation
- `docs/` is the Obsidian vault. Entry points: `ARCHITECTURE.md`, `docs/architecture/README.md`, `docs/development/README.md`.
- Keep documentation consistent with the implementation.

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
