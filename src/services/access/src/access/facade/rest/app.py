"""REST facade (``api`` process type): the public read API plus liveness and readiness."""

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
from pydantic import AwareDatetime

from access.application.ports import CurveReader
from access.domain.curve import (
    CurveNotFoundError,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.facade.mapping import to_response, to_series_response
from access.facade.rest.caching import json_with_etag

PROBLEM_JSON = "application/problem+json"
UNAVAILABLE_DETAIL = "The curve store is not reachable; try again later."
NOT_MODIFIED = "Not modified: the ETag matches If-None-Match"


@dataclass(frozen=True, slots=True)
class Services:
    """What the facade needs from the rest of the service."""

    is_ready: Callable[[], Awaitable[bool]]
    curves: CurveReader


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
        curve = await services.curves.curve_as_of(curve_id, valid_date, as_of)
        return json_with_etag(request, to_response(curve))

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
        series = await services.curves.series_as_of(curve_id, maturity, valid_from, valid_to, as_of)
        return json_with_etag(request, to_series_response(series))

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


def _problem(status_code: int, title: str, detail: str, **extensions: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status_code, "detail": detail}
    return JSONResponse(body | extensions, status_code=status_code, media_type=PROBLEM_JSON)
