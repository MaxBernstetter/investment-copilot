# Development Principles

How to plan and implement a piece of software in YieldLens: a service, a feature, a fix. The principles apply to humans and coding agents alike.

## Workflow at a glance

1. **Plan:** check applicability, then cut the smallest vertical slice ([[02-applicability]], [[03-simplicity]]).
2. **Design:** respect service boundaries and the twelve factors ([[01-twelve-factor]], `ARCHITECTURE.md`).
3. **Implement:** clean code, readable first ([[04-clean-code]]).
4. **Validate:** prove it works, at the right test level ([[05-testing]]).
5. **Check scale:** confirm the design holds at 100× ([[06-scalability]]).
6. **Ship safely:** CI checks, deployment and security rules ([[07-delivery-and-security]]).
7. **Finish:** check the [[#Definition of done]], then close the task ([[01-task-management]]).

## Principles

1. [[01-twelve-factor]]: building services that deploy and scale cleanly
2. [[02-applicability]]: does this piece solve the actual problem, here and now?
3. [[03-simplicity]]: the simplest thing that works, and no more
4. [[04-clean-code]]: code that reads like the domain
5. [[05-testing]]: how to validate a piece of software is working
6. [[06-scalability]]: designing for 100× without building for it today
7. [[07-delivery-and-security]]: CI/CD, deployment and security rules

## Definition of done

- [ ] Solves the issue's problem, and acceptance criteria are met
- [ ] Simplest viable design; no speculative features
- [ ] Twelve-factor compliant; no cross-service imports or schema access
- [ ] Every acceptance criterion is covered by a test ([[05-testing]])
- [ ] Tests at the right levels pass locally and in CI; no flaky or skipped tests added
- [ ] Required CI checks pass; no secrets committed ([[07-delivery-and-security]])
- [ ] Transparency in place: transparency interface, domain metrics, business alerts, dashboard, JSON logs, traces, `/health` and `/ready` (see `docs/architecture/10-observability.md`)
- [ ] Behaviour observable in operation after deployment
- [ ] No design choice blocks 100× scale
- [ ] Docs updated; diff reviewed
