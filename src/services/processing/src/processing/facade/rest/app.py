"""REST facade (``api`` process type): quality reads, derived measures, liveness and readiness."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Any

from contracts.processing import v1
from fastapi import Depends, FastAPI, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from opentelemetry import trace
from pydantic import AwareDatetime

from processing.application.check_quality import CheckQuality, UnknownCurveError
from processing.application.get_measures import GetMeasures
from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.domain.read import MAX_DAYS_RANGE, FutureAsOfError, InvalidRangeError
from processing.facade.mapping import (
    to_measures_response,
    to_quality_check_response,
    to_quality_days_response,
    to_value_quality_response,
)
from processing.facade.rest.caching import cache_control, json_with_etag

PROBLEM_JSON = "application/problem+json"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]
    get_quality_days: GetQualityDays
    get_value_quality: GetValueQuality
    get_measures: GetMeasures
    check_quality: CheckQuality


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
            status.HTTP_404_NOT_FOUND: {"description": "The curve is unknown"},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"},
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

    @app.post(
        v1.QUALITY_CHECKS_PATH,
        response_model=v1.QualityCheckResponse,
        responses={
            status.HTTP_404_NOT_FOUND: {"description": "The curve is unknown"},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"},
        },
    )
    async def quality_check(
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        body: v1.QualityCheckRequest,
        services: ServicesDependency,
    ) -> v1.QualityCheckResponse:
        """Check the quality of a curve over a valid-date range now and record the result."""
        if body.valid_to < body.valid_from or body.valid_to - body.valid_from >= MAX_DAYS_RANGE:
            raise InvalidRangeError(
                f"valid_from must not be after valid_to, and the range at most "
                f"{MAX_DAYS_RANGE.days} days"
            )
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        run_id = f"ui-check-{curve_id}-{body.valid_from}-{body.valid_to}-{stamp}"
        result = await services.check_quality(curve_id, body.valid_from, body.valid_to, run_id)
        return to_quality_check_response(result)

    @app.get(
        v1.VALUE_QUALITY_PATH,
        response_model=v1.ValueQualityResponse,
        responses={
            status.HTTP_404_NOT_FOUND: {"description": "The curve is unknown"},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"},
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

    @app.get(
        v1.MEASURES_PATH,
        response_model=v1.MeasuresResponse,
        responses={
            status.HTTP_404_NOT_FOUND: {"description": "The curve is unknown"},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The request is invalid"},
        },
    )
    async def measures(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        valid_from: Annotated[date, Query(alias="from")],
        valid_to: Annotated[date, Query(alias="to")],
        services: ServicesDependency,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """Spreads, curvature and inversion per valid date, as known at ``meta.as_of``."""
        result = await services.get_measures(curve_id, valid_from, valid_to, as_of)
        response = to_measures_response(result)
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

    @app.exception_handler(UnknownCurveError)
    async def unknown_curve(_: Request, error: UnknownCurveError) -> JSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Not found", str(error))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        trace_fields = _trace_fields()
        logger.exception(
            "Unexpected error",
            extra={
                "event": "unexpected_error",
                "method": request.method,
                "path": request.url.path,
            }
            | trace_fields,
        )
        return _problem(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
            "An unexpected error occurred.",
            **trace_fields,
        )


def _trace_fields() -> dict[str, str]:
    context = trace.get_current_span().get_span_context()
    return {"trace_id": trace.format_trace_id(context.trace_id)} if context.is_valid else {}


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
