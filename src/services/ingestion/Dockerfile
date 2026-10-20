# Ingestion image: the `api` process (default CMD, port 8003) and the jobs
# `ingestion-load-ecb` / `ingestion-scenario` (set as entrypoint by compose and Airflow).
# Build context is src/ (the service needs contracts/). Built by `task dev:up` and run by
# `task dev:seed` through src/deploy/compose.yaml.
# Published to GHCR by `task ingestion:image` (.github/workflows/images.yml).

FROM python:3.13.16-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src/services/ingestion

# Dependencies first (cached while the lockfile is unchanged), then the project.
COPY contracts /src/contracts
COPY services/ingestion/pyproject.toml services/ingestion/uv.lock ./
RUN uv sync --locked --no-dev --no-editable --no-install-project
COPY services/ingestion/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.16-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/MaxBernstetter/yield-lens"

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
COPY services/ingestion/log_config.json /app/log_config.json
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8003
CMD ["uvicorn", "--factory", "ingestion.api:create_app_from_environment", "--host", "0.0.0.0", "--port", "8003", "--log-config", "/app/log_config.json"]
