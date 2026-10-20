# Persistence service image. Build context is src/ (the service needs contracts/).
# Built by `task dev:up` through src/deploy/compose.yaml.
# Published to GHCR by `task persistence:image` (.github/workflows/images.yml).

FROM python:3.13.16-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src/services/persistence

# Dependencies first (cached while the lockfile is unchanged), then the project.
COPY contracts /src/contracts
COPY services/persistence/pyproject.toml services/persistence/uv.lock ./
RUN uv sync --locked --no-dev --no-editable --no-install-project
COPY services/persistence/src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.16-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/MaxBernstetter/yield-lens"

RUN pip install --no-cache-dir --root-user-action=ignore \
    setuptools==78.1.1 urllib3==2.8.0 msgpack==1.2.1 \
    && pip uninstall -y pip setuptools

RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
COPY services/persistence/log_config.json /app/log_config.json
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8001
CMD ["uvicorn", "--factory", "persistence.api:create_app_from_environment", "--host", "0.0.0.0", "--port", "8001", "--log-config", "/app/log_config.json"]
