# Delivery and Security

How changes get from a commit to the live system, and the security rules every piece follows. Deployment topology is described in `docs/architecture/09-deployment.md`.

## CI/CD

- **Change detection:** path-filtered GitHub Actions jobs per service and for `contracts`. A contract change triggers all consumers.
- **Required checks:** lint, types, tests, import-linter, contract tests, DAG integrity tests.
- **Artifacts:** multi-arch (amd64/arm64) images pushed to GHCR, tagged with the commit SHA.
- **Deploy:**
  - Frontend: build → GitHub Pages.
  - Backend: SSH to the VM → `docker compose pull && docker compose up -d` → Liquibase migrations → readiness check.

## Security

- No secrets in the repository. Use GitHub Secrets and a `.env` on the VM (not committed).
- One least-privilege DB user per schema.
- Only `access` is public: read-only, rate-limited, CORS restricted to the Pages origin.
- Internal APIs and the Airflow UI are reachable only through an SSH tunnel.
- Dependency and image scanning in CI (Dependabot, Trivy).

## Checks when planning a piece

- Does it need a new secret? It goes into GitHub Secrets or the VM `.env`, never into the repo.
- Does it expose anything new publicly? Only through `access`.
- Is it covered by the path filters and required checks?
