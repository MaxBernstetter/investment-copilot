# Ingestion job image (one-shot ECB loads, no server). Build context is src/ (the service
# needs contracts/). Built by `task dev:up` and run by `task dev:seed` through
# src/deploy/compose.yaml. Entry point: the ingestion-load-ecb console script.

FROM python:3.13.9-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src/services/ingestion

# Dependencies first (cached while the lockfile is unchanged), then the project.
COPY contracts /src/contracts
COPY services/ingestion/pyproject.toml services/ingestion/uv.lock ./
RUN uv sync --locked --no-dev --no-editable --no-install-project
COPY services/ingestion/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.9-slim-bookworm

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
ENTRYPOINT ["ingestion-load-ecb"]
