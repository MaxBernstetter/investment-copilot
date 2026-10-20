"""REST facade (``api`` process type): liveness and readiness."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from contracts.transparency.v1 import (
    DEFAULT_RUNS_LIMIT,
    MAX_RUNS_LIMIT,
    RUN_PATH,
    RUNS_PATH,
    RunAttemptsResponse,
    RunsMeta,
    RunsResponse,
)
from fastapi import FastAPI, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ingestion.application.run_history import RunHistory, list_runs
from ingestion.facade.rest.runs import to_run

PROBLEM_JSON = "application/problem+json"
PROBLEM_RESPONSE: dict[str, Any] = {"content": {PROBLEM_JSON: {}}}


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]
    runs: RunHistory


ServicesProvider = Callable[[], AbstractAsyncContextManager[Services]]


def create_app(services: ServicesProvider) -> FastAPI:
    """Build the app; ``services`` opens and closes the backing resources with the app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services() as opened:
            app.state.services = opened
            yield

    app = FastAPI(title="YieldLens ingestion", version="1", lifespan=lifespan)
    _add_problem_handlers(app)
    _add_routes(app)
    return app


def _add_routes(app: FastAPI) -> None:
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/ready", responses={status.HTTP_503_SERVICE_UNAVAILABLE: {}})
    async def ready(request: Request) -> JSONResponse:
        """Readiness: the ING schema is reachable."""
        services: Services = request.app.state.services
        if await services.is_ready():
            return JSONResponse({"status": "ready"})
        return JSONResponse(
            {"status": "unavailable"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    @app.get(
        RUNS_PATH,
        response_model=RunsResponse,
        responses={422: {"description": "Invalid query", **PROBLEM_RESPONSE}},
    )
    async def list_runs_endpoint(
        request: Request,
        from_: Annotated[date | None, Query(alias="from")] = None,
        to: date | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_RUNS_LIMIT)] = DEFAULT_RUNS_LIMIT,
        cursor: Annotated[str | None, Query(pattern=r"^[1-9][0-9]{0,17}$")] = None,
    ) -> RunsResponse | JSONResponse:
        """Attempts of this service, newest first; ``from`` and ``to`` are inclusive UTC dates."""
        if from_ is not None and to is not None and from_ > to:
            return _problem(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Invalid request",
                "`from` must not be after `to`.",
            )
        services: Services = request.app.state.services
        page = await list_runs(
            services.runs,
            from_date=from_,
            to_date=to,
            before_attempt_id=None if cursor is None else int(cursor),
            limit=limit,
        )
        next_cursor = None if page.next_cursor is None else str(page.next_cursor)
        return RunsResponse(
            data=[to_run(attempt) for attempt in page.attempts],
            meta=RunsMeta(next_cursor=next_cursor),
        )

    @app.get(
        RUN_PATH,
        response_model=RunAttemptsResponse,
        responses={404: {"description": "Unknown run", **PROBLEM_RESPONSE}},
    )
    async def get_run(
        request: Request,
        run_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> RunAttemptsResponse | JSONResponse:
        """Every attempt of one run id, in attempt order."""
        services: Services = request.app.state.services
        attempts = await services.runs.get_attempts(run_id)
        if not attempts:
            return _problem(
                status.HTTP_404_NOT_FOUND,
                "Run not found",
                f"No attempt of run {run_id} is recorded.",
            )
        return RunAttemptsResponse(data=[to_run(attempt) for attempt in attempts])


def _add_problem_handlers(app: FastAPI) -> None:
    """Errors are RFC 9457 problem details."""

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, error: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in error.errors()
        ]
        return _problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid request",
            "The request does not match the contract.",
            errors=errors,
        )


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
