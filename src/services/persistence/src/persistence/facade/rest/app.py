"""REST facade (``api`` process type): the write interface plus liveness and readiness."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any

from contracts.persistence import v1
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from persistence.application.record_versions import RecordVersions
from persistence.domain.observation import InvalidObservationsError, OpenVersionExistsError
from persistence.facade.mapping import to_observation, to_response

PROBLEM_JSON = "application/problem+json"


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    record_versions: RecordVersions
    is_ready: Callable[[], Awaitable[bool]]


ServicesProvider = Callable[[], AbstractAsyncContextManager[Services]]


def create_app(services: ServicesProvider) -> FastAPI:
    """Build the app; ``services`` opens and closes the backing resources with the app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services() as opened:
            app.state.services = opened
            yield

    app = FastAPI(title="YieldLens persistence", version="1", lifespan=lifespan)
    _add_problem_handlers(app)
    _add_routes(app)
    return app


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDependency = Annotated[Services, Depends(_services)]


def _add_routes(app: FastAPI) -> None:
    @app.post(
        v1.RECORD_VERSIONS_PATH,
        response_model=v1.RecordVersionsResponse,
        status_code=status.HTTP_200_OK,
        responses={
            status.HTTP_409_CONFLICT: {"description": "An observation already has an open version"},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The batch is invalid"},
        },
    )
    async def record_versions(
        request: v1.RecordVersionsRequest, services: ServicesDependency
    ) -> v1.RecordVersionsResponse:
        """Record every observation of the batch as a new version (all or nothing)."""
        recorded = await services.record_versions(
            [to_observation(version) for version in request.observations]
        )
        return to_response(recorded)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/ready", responses={status.HTTP_503_SERVICE_UNAVAILABLE: {}})
    async def ready(services: ServicesDependency) -> JSONResponse:
        """Readiness: the database is reachable."""
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

    @app.exception_handler(InvalidObservationsError)
    async def invalid_observations(_: Request, error: InvalidObservationsError) -> JSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid observations", str(error))

    @app.exception_handler(OpenVersionExistsError)
    async def open_version_exists(_: Request, error: OpenVersionExistsError) -> JSONResponse:
        return _problem(
            status.HTTP_409_CONFLICT,
            "Open version exists",
            "An observation of the batch already has an open version; nothing was recorded.",
        )


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
