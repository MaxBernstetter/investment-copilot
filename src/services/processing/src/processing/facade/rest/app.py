"""REST facade (``api`` process type): quality reads, liveness and readiness."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from contracts.processing import v1
from fastapi import Depends, FastAPI, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import AwareDatetime

from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.domain.read import FutureAsOfError, InvalidRangeError
from processing.facade.mapping import to_quality_days_response, to_value_quality_response
from processing.facade.rest.caching import cache_control, json_with_etag

PROBLEM_JSON = "application/problem+json"


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]
    get_quality_days: GetQualityDays
    get_value_quality: GetValueQuality


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


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDependency = Annotated[Services, Depends(_services)]


def _add_routes(app: FastAPI) -> None:
    @app.get(
        v1.QUALITY_DAYS_PATH,
        response_model=v1.QualityDaysResponse,
        responses={
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"}
        },
    )
    async def quality_days(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        valid_from: Annotated[date, Query(alias="from")],
        valid_to: Annotated[date, Query(alias="to")],
        services: ServicesDependency,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """Quality of each TARGET business day of a curve as known at ``as_of`` (default: now)."""
        days = await services.get_quality_days(curve_id, valid_from, valid_to, as_of)
        response = to_quality_days_response(days)
        return json_with_etag(
            request,
            response,
            cache_control=cache_control(as_of, response.meta.as_of),
        )

    @app.get(
        v1.VALUE_QUALITY_PATH,
        response_model=v1.ValueQualityResponse,
        responses={
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"}
        },
    )
    async def value_quality(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        valid_from: Annotated[date, Query(alias="from")],
        valid_to: Annotated[date, Query(alias="to")],
        services: ServicesDependency,
        maturity: Annotated[str | None, Query(min_length=1, max_length=16)] = None,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """Quality of published values of a curve as known at ``as_of`` (default: now)."""
        values = await services.get_value_quality(
            curve_id, valid_from, valid_to, as_of, maturity=maturity
        )
        response = to_value_quality_response(values)
        return json_with_etag(
            request,
            response,
            cache_control=cache_control(as_of, response.meta.as_of),
        )

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

    @app.exception_handler(InvalidRangeError)
    async def invalid_range(_: Request, error: InvalidRangeError) -> JSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid range", str(error))

    @app.exception_handler(FutureAsOfError)
    async def future_as_of(_: Request, error: FutureAsOfError) -> JSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid as_of", str(error))


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
