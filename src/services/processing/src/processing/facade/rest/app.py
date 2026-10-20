"""REST facade (``api`` process type): liveness and readiness."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_JSON = "application/problem+json"


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]


ServicesProvider = Callable[[], AbstractAsyncContextManager[Services]]


def create_app(services: ServicesProvider) -> FastAPI:
    """Build the app; ``services`` opens and closes the backing resources with the app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services() as opened:
            app.state.services = opened
            yield

    app = FastAPI(title="YieldLens processing", version="1", lifespan=lifespan)
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
        """Readiness: the processing database is reachable."""
        services: Services = request.app.state.services
        if await services.is_ready():
            return JSONResponse({"status": "ready"})
        return JSONResponse(
            {"status": "unavailable"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


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
