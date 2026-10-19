# Access service image. Build context is src/ (the service needs contracts/).
# Built by `task dev:up` through src/deploy/compose.yaml.

FROM python:3.13.9-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src/services/access

# Dependencies first (cached while the lockfile is unchanged), then the project.
COPY contracts /src/contracts
COPY services/access/pyproject.toml services/access/uv.lock ./
RUN uv sync --locked --no-dev --no-editable --no-install-project
COPY services/access/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.9-slim-bookworm

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
COPY services/access/log_config.json /app/log_config.json
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "--factory", "access.api:create_app_from_environment", "--host", "0.0.0.0", "--port", "8000", "--log-config", "/app/log_config.json"]
