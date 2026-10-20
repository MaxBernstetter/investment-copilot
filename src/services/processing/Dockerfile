# Processing service image. Build context is src/ (the service needs contracts/).
# Compose wiring: src/deploy/compose.yaml (service processing, started by dev:up).

FROM python:3.13.9-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src/services/processing

# Dependencies first (cached while the lockfile is unchanged), then the project.
COPY contracts /src/contracts
COPY services/processing/pyproject.toml services/processing/uv.lock ./
RUN uv sync --locked --no-dev --no-editable --no-install-project
COPY services/processing/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.9-slim-bookworm

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
COPY services/processing/log_config.json /app/log_config.json
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8002
CMD ["uvicorn", "--factory", "processing.api:create_app_from_environment", "--host", "0.0.0.0", "--port", "8002", "--log-config", "/app/log_config.json"]
