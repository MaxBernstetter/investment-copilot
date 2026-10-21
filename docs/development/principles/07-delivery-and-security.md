# Delivery and Security

How changes get from a commit to the live system, and the security rules every piece follows. Deployment topology is described in `docs/architecture/09-deployment.md`.

## CI/CD

- **One way to run tasks:**
  - Every task runs through `task` (go-task) with the devbox toolchain.
  - CI workflows only call tasks, so every CI step can be run locally with the same command.
  - Taskfiles only glue; logic lives in tested, linted scripts. See `docs/architecture/13-build-and-ci.md`.
- **Hooks:** pre-commit runs fast checks at commit time; CI re-runs all hooks on all files.
- **Change detection:** path-filtered GitHub Actions jobs per service and for `contracts`. A contract change triggers all consumers.
- **Required checks:** lint, types, tests, import-linter, contract tests, DAG integrity tests.
- **Artifacts:** multi-arch (amd64/arm64) images pushed to GHCR, tagged with the commit SHA.
- **Deploy:**
  - Frontend: build → GitHub Pages.
  - Backend: SSH to the VM → checkout of the deployed commit → `task deploy:all` (GHCR login with a read-only token, pull, Liquibase migrations, `up -d`, readiness check).

## Security

- No secrets in the repository. Use GitHub Secrets and a `.env` on the VM (not committed).
- One least-privilege DB user per schema.
- Only `access` is public: read-only, rate-limited, CORS restricted to the Pages origin.
- Internal APIs, the Airflow UI and Grafana are reachable only through an SSH tunnel.
- Dependency and image scanning in CI (Dependabot, Trivy); an image with a fixable HIGH or CRITICAL vulnerability is not published.
- Workflows pin actions to commit SHAs, use least-privilege token permissions, and never persist checkout credentials.

## Checks when planning a piece

- Does it need a new secret? It goes into GitHub Secrets or the VM `.env`, never into the repo.
- Does it expose anything new publicly? Only through `access`.
- Is it covered by the path filters and required checks?
- Can every new CI step be run locally with one `task` command? Is any logic in a Taskfile or workflow that belongs in a script?
