"""REST facade (``api`` process type): the write interface plus liveness and readiness."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from contracts.persistence import v1
from fastapi import Depends, FastAPI, Path, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime

from persistence.application.get_curve_as_of import GetCurveAsOf
from persistence.application.record_versions import RecordVersions
from persistence.domain.curve import FutureAsOfError, NothingKnownError
from persistence.domain.observation import InvalidObservationsError, OpenVersionExistsError
from persistence.facade.mapping import to_curve_response, to_observation, to_response

PROBLEM_JSON = "application/problem+json"


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    record_versions: RecordVersions
    is_ready: Callable[[], Awaitable[bool]]
    get_curve_as_of: GetCurveAsOf


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
            status.HTTP_409_CONFLICT: {
                "description": "A concurrent write recorded the same observation first; retry"
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The batch is invalid"},
        },
    )
    async def record_versions(
        request: v1.RecordVersionsRequest, services: ServicesDependency
    ) -> v1.RecordVersionsResponse:
        """Record the batch as versions (all or nothing); unchanged observations are no-ops."""
        recorded = await services.record_versions(
            [to_observation(version) for version in request.observations]
        )
        return to_response(recorded)

    @app.get(
        v1.CURVE_OBSERVATIONS_PATH,
        response_model=v1.CurveObservationsResponse,
        responses={
            status.HTTP_404_NOT_FOUND: {
                "description": "No published value of the curve is known as of the time"
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"},
        },
    )
    async def curve_observations(
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        services: ServicesDependency,
        valid_date: date | None = None,
        as_of: AwareDatetime | None = None,
    ) -> v1.CurveObservationsResponse:
        """One published curve as it was known at ``as_of`` (default: now).

        ``valid_date`` defaults to the latest valid date known at ``as_of``.
        """
        curve = await services.get_curve_as_of(curve_id, valid_date, as_of)
        return to_curve_response(curve)

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

    @app.exception_handler(NothingKnownError)
    async def nothing_known(_: Request, error: NothingKnownError) -> JSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Not found", str(error))

    @app.exception_handler(FutureAsOfError)
    async def future_as_of(_: Request, error: FutureAsOfError) -> JSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid as_of", str(error))

    @app.exception_handler(OpenVersionExistsError)
    async def open_version_exists(_: Request, error: OpenVersionExistsError) -> JSONResponse:
        return _problem(
            status.HTTP_409_CONFLICT,
            "Concurrent write",
            "A concurrent write recorded an observation of the batch first; nothing was "
            "recorded. Send the batch again.",
        )


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
