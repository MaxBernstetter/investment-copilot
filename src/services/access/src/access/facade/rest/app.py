"""REST facade (``api`` process type): the public read API, the catalogue, liveness, readiness."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from contracts.access import v1
from fastapi import Depends, FastAPI, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from pydantic import AwareDatetime

from access.application.catalogue import CachedCatalogue
from access.application.ports import CurveReader, MeasuresReader, QualityReader
from access.domain.curve import (
    CurveNotFoundError,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
    ProcessingUnavailableError,
)
from access.domain.measures import MeasuresUnavailableError, inputs_are_checked
from access.domain.quality import quality_is_complete
from access.facade.mapping import (
    to_changes_response,
    to_curves_response,
    to_measures_response,
    to_quality_days_response,
    to_response,
    to_series_response,
    to_versions_response,
)
from access.facade.rest.caching import CATALOGUE, NO_CACHE, cache_control, json_with_etag

PROBLEM_JSON = "application/problem+json"
UNAVAILABLE_DETAIL = "The curve store is not reachable; try again later."
QUALITY_UNAVAILABLE_DETAIL = "The quality service is not reachable; try again later."
MEASURES_UNAVAILABLE_DETAIL = "The measures service is not reachable; try again later."
NOT_MODIFIED = "Not modified: the ETag matches If-None-Match"
UNEXPECTED_DETAIL = "An unexpected error occurred."

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]
    curves: CurveReader
    quality: QualityReader
    catalogue: CachedCatalogue
    measures: MeasuresReader


ServicesProvider = Callable[[], AbstractAsyncContextManager[Services]]


def create_app(services: ServicesProvider, *, cors_origins: Sequence[str]) -> FastAPI:
    """Build the app; ``services`` opens and closes the backing resources with the app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with services() as opened:
            app.state.services = opened
            yield

    app = FastAPI(title="YieldLens access", version="1", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["GET"],
        allow_headers=[],
    )
    _add_problem_handlers(app)
    _add_routes(app)
    return app


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDependency = Annotated[Services, Depends(_services)]


def _add_routes(app: FastAPI) -> None:
    @app.get(
        v1.CURVES_PATH,
        response_model=v1.CurvesResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
        },
    )
    async def curve_catalogue(request: Request, services: ServicesDependency) -> Response:
        """The curve catalogue: every curve with its source, conventions, attribution and grid."""
        return json_with_etag(
            request,
            to_curves_response(await services.catalogue.curves()),
            cache_control=CATALOGUE,
        )

    @app.get(
        v1.CURVE_OBSERVATIONS_PATH,
        response_model=v1.CurveObservationsResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
        },
    )
    async def curve_observations(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        services: ServicesDependency,
        valid_date: date | None = None,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """One curve on one valid date, as it was known at ``meta.as_of``.

        Without ``valid_date`` or ``as_of`` the store picks its defaults; the answer
        reports the knowledge time it used in ``meta.as_of``.
        """
        attribution = await services.catalogue.attribution(curve_id)
        curve = await services.curves.curve_as_of(curve_id, valid_date, as_of)
        known = await services.quality.value_quality(
            curve_id, curve.valid_date, curve.valid_date, None, curve.as_of
        )
        version_ids = {point.version_id for point in curve.points if point.version_id is not None}
        complete = quality_is_complete(version_ids, known)
        return json_with_etag(
            request,
            to_response(curve, known=known, attribution=attribution),
            cache_control=cache_control(as_of, curve.as_of, complete=complete),
        )

    @app.get(
        v1.SERIES_OBSERVATIONS_PATH,
        response_model=v1.SeriesObservationsResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
        },
    )
    async def series_observations(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        maturity: Annotated[str, Path(min_length=1, max_length=16)],
        services: ServicesDependency,
        valid_from: Annotated[date | None, Query(alias="from")] = None,
        valid_to: Annotated[date | None, Query(alias="to")] = None,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """One maturity of a curve over valid dates, as it was known at ``meta.as_of``.

        Without ``from``, ``to`` or ``as_of`` the store picks its defaults; the answer
        reports the knowledge time it used in ``meta.as_of``.
        """
        attribution = await services.catalogue.attribution(curve_id)
        series = await services.curves.series_as_of(curve_id, maturity, valid_from, valid_to, as_of)
        if series.points:
            dates = [point.valid_date for point in series.points]
            known = await services.quality.value_quality(
                curve_id, min(dates), max(dates), maturity, series.as_of
            )
            version_ids = {point.version_id for point in series.points}
            complete = quality_is_complete(version_ids, known)
        else:
            known = None
            complete = True
        return json_with_etag(
            request,
            to_series_response(series, known=known, attribution=attribution),
            cache_control=cache_control(as_of, series.as_of, complete=complete),
        )

    @app.get(
        v1.VALUE_VERSIONS_PATH,
        response_model=v1.ValueVersionsResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
        },
    )
    async def value_versions(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        maturity: Annotated[str, Path(min_length=1, max_length=16)],
        valid_date: date,
        services: ServicesDependency,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """The version history of one value as it was known at ``meta.as_of``.

        Versions are listed oldest first; ``known_to`` is null while a version is current.
        Without ``as_of`` the store picks its default; the answer reports the knowledge
        time it used in ``meta.as_of``.
        """
        attribution = await services.catalogue.attribution(curve_id)
        versions = await services.curves.value_versions(curve_id, maturity, valid_date, as_of)
        return json_with_etag(
            request,
            to_versions_response(versions, attribution=attribution),
            cache_control=cache_control(as_of, versions.as_of),
        )

    @app.get(
        v1.CURVE_CHANGES_PATH,
        response_model=v1.CurveChangesResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
        },
    )
    async def curve_changes(
        request: Request,
        curve_id: Annotated[str, Path(min_length=1, max_length=64)],
        valid_from: Annotated[date, Query(alias="from")],
        valid_to: Annotated[date, Query(alias="to")],
        since: AwareDatetime,
        services: ServicesDependency,
        as_of: AwareDatetime | None = None,
    ) -> Response:
        """What changed in a curve over valid dates between ``since`` and ``as_of``.

        A change is a value whose visible version differs between the two knowledge times;
        ``old_value`` is null when the value was not known at ``since``. Without ``as_of``
        the store picks its default; the answer reports both knowledge times in ``meta``.
        """
        attribution = await services.catalogue.attribution(curve_id)
        changes = await services.curves.changes(curve_id, valid_from, valid_to, since, as_of)
        return json_with_etag(
            request,
            to_changes_response(changes, attribution=attribution),
            cache_control=cache_control(as_of, changes.as_of),
        )

    @app.get(
        v1.QUALITY_PATH,
        response_model=v1.QualityDaysResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
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
        """Quality of each TARGET business day of a curve as known at ``meta.as_of``.

        ``from`` and ``to`` bound the valid-date range (inclusive). Without ``as_of`` processing
        picks its default; the answer reports the knowledge time it used in ``meta.as_of``.
        """
        attribution = await services.catalogue.attribution(curve_id)
        days = await services.quality.quality_days(curve_id, valid_from, valid_to, as_of)
        return json_with_etag(
            request,
            to_quality_days_response(days, attribution=attribution),
            cache_control=NO_CACHE,
        )

    @app.get(
        v1.MEASURES_PATH,
        response_model=v1.MeasuresResponse,
        responses={
            status.HTTP_304_NOT_MODIFIED: {"description": NOT_MODIFIED},
            status.HTTP_404_NOT_FOUND: {"model": v1.Problem},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": v1.Problem},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": v1.Problem},
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
        """Spreads, curvature and inversion per valid date, as known at ``meta.as_of``.

        Relayed from processing. ``from`` and ``to`` bound the valid-date range (inclusive).
        Without ``as_of`` processing picks its default; the answer reports the knowledge time
        it used in ``meta.as_of``.
        """
        result = await services.measures.measures(curve_id, valid_from, valid_to, as_of)
        attribution = await services.catalogue.attribution(curve_id)
        return json_with_etag(
            request,
            to_measures_response(result, attribution=attribution),
            cache_control=cache_control(as_of, result.as_of, complete=inputs_are_checked(result)),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/ready", responses={status.HTTP_503_SERVICE_UNAVAILABLE: {}})
    async def ready(services: ServicesDependency) -> JSONResponse:
        """Readiness: the persistence service is reachable and ready."""
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

    @app.exception_handler(CurveNotFoundError)
    async def curve_not_found(_: Request, error: CurveNotFoundError) -> JSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Not found", error.detail)

    @app.exception_handler(InvalidCurveQueryError)
    async def invalid_curve_query(_: Request, error: InvalidCurveQueryError) -> JSONResponse:
        return _problem(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", error.detail)

    @app.exception_handler(PersistenceUnavailableError)
    async def persistence_unavailable(
        _: Request, _error: PersistenceUnavailableError
    ) -> JSONResponse:
        return _problem(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable", UNAVAILABLE_DETAIL
        )

    @app.exception_handler(ProcessingUnavailableError)
    async def processing_unavailable(
        _: Request, _error: ProcessingUnavailableError
    ) -> JSONResponse:
        return _problem(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable", QUALITY_UNAVAILABLE_DETAIL
        )

    @app.exception_handler(MeasuresUnavailableError)
    async def measures_unavailable(_: Request, _error: MeasuresUnavailableError) -> JSONResponse:
        return _problem(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable", MEASURES_UNAVAILABLE_DETAIL
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        trace_fields = _trace_fields()
        logger.exception(
            "Unexpected error",
            exc_info=error,
            extra={"event": "unexpected_error", "method": request.method, "path": request.url.path}
            | trace_fields,
        )
        return _problem(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
            UNEXPECTED_DETAIL,
            **trace_fields,
        )


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)


def _trace_fields() -> dict[str, str]:
    context = trace.get_current_span().get_span_context()
    return {"trace_id": trace.format_trace_id(context.trace_id)} if context.is_valid else {}
