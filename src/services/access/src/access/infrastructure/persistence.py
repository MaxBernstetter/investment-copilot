"""Client of the persistence service: readiness and the curve read interface."""

from datetime import date, datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx
from contracts.persistence import v1
from pydantic import ValidationError

from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.domain.series import Series, SeriesPoint
from access.domain.versions import ChangeReason, ValueVersion, ValueVersions

HTTP_UNPROCESSABLE_CONTENT = 422


class PersistenceClient:
    """Calls the persistence service: readiness, and curves as of a knowledge time."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def is_ready(self) -> bool:
        """True only when persistence answers ``200`` on ``/ready``; unreachable is not ready."""
        try:
            response = await self._http.get("/ready")
        except httpx.HTTPError:
            return False
        return response.status_code == httpx.codes.OK

    async def curve_as_of(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf:
        """Read one curve; absent parameters are left to persistence (its defaults)."""
        path = v1.CURVE_OBSERVATIONS_PATH.format(curve_id=quote(curve_id, safe=""))
        params: dict[str, str] = {}
        if valid_date is not None:
            params["valid_date"] = valid_date.isoformat()
        if as_of is not None:
            params["as_of"] = as_of.isoformat()
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise PersistenceUnavailableError from error

        if response.status_code == httpx.codes.OK:
            return _to_domain(_parse(response))
        if response.status_code == httpx.codes.NOT_FOUND:
            raise CurveNotFoundError(_problem_detail(response))
        if response.status_code == HTTP_UNPROCESSABLE_CONTENT:
            raise InvalidCurveQueryError(_problem_detail(response))
        raise PersistenceUnavailableError(f"persistence answered {response.status_code}")

    async def series_as_of(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date | None,
        valid_to: date | None,
        as_of: datetime | None,
    ) -> Series:
        """Read one maturity over valid dates; absent parameters are left to persistence."""
        path = v1.SERIES_OBSERVATIONS_PATH.format(
            curve_id=quote(curve_id, safe=""), maturity=quote(maturity, safe="")
        )
        params: dict[str, str] = {}
        if valid_from is not None:
            params["from"] = valid_from.isoformat()
        if valid_to is not None:
            params["to"] = valid_to.isoformat()
        if as_of is not None:
            params["as_of"] = as_of.isoformat()
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise PersistenceUnavailableError from error

        if response.status_code == httpx.codes.OK:
            return _series_to_domain(_parse_series(response))
        if response.status_code == httpx.codes.NOT_FOUND:
            raise CurveNotFoundError(_problem_detail(response))
        if response.status_code == HTTP_UNPROCESSABLE_CONTENT:
            raise InvalidCurveQueryError(_problem_detail(response))
        raise PersistenceUnavailableError(f"persistence answered {response.status_code}")

    async def value_versions(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime | None
    ) -> ValueVersions:
        """Read the version history of one value; absent ``as_of`` is left to persistence."""
        path = v1.VALUE_VERSIONS_PATH.format(
            curve_id=quote(curve_id, safe=""),
            maturity=quote(maturity, safe=""),
            valid_date=valid_date.isoformat(),
        )
        params: dict[str, str] = {}
        if as_of is not None:
            params["as_of"] = as_of.isoformat()
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise PersistenceUnavailableError from error

        if response.status_code == httpx.codes.OK:
            return _versions_to_domain(_parse_versions(response))
        if response.status_code == httpx.codes.NOT_FOUND:
            raise CurveNotFoundError(_problem_detail(response))
        if response.status_code == HTTP_UNPROCESSABLE_CONTENT:
            raise InvalidCurveQueryError(_problem_detail(response))
        raise PersistenceUnavailableError(f"persistence answered {response.status_code}")


def _parse_versions(response: httpx.Response) -> v1.ValueVersionsResponse:
    try:
        return v1.ValueVersionsResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise PersistenceUnavailableError("persistence sent an unexpected versions body") from error


def _versions_to_domain(body: v1.ValueVersionsResponse) -> ValueVersions:
    return ValueVersions(
        curve_id=body.data.curve_id,
        maturity=body.data.maturity,
        valid_date=body.data.valid_date,
        as_of=body.meta.as_of,
        versions=tuple(
            ValueVersion(
                version_id=version.version_id,
                value=version.value,
                known_from=version.known_from,
                known_to=version.known_to,
                source_id=version.source_id,
                run_id=version.run_id,
                change_reason=ChangeReason(version.change_reason.value),
                normalization_version=version.normalization_version,
                delivery_id=version.delivery_id,
            )
            for version in body.data.versions
        ),
    )


def _parse_series(response: httpx.Response) -> v1.SeriesObservationsResponse:
    try:
        return v1.SeriesObservationsResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise PersistenceUnavailableError("persistence sent an unexpected series body") from error


def _series_to_domain(body: v1.SeriesObservationsResponse) -> Series:
    return Series(
        curve_id=body.data.curve_id,
        maturity=body.data.maturity,
        as_of=body.meta.as_of,
        points=tuple(
            SeriesPoint(valid_date=point.valid_date, value=point.value)
            for point in body.data.points
        ),
    )


def _parse(response: httpx.Response) -> v1.CurveObservationsResponse:
    try:
        return v1.CurveObservationsResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise PersistenceUnavailableError("persistence sent an unexpected curve body") from error


def _to_domain(body: v1.CurveObservationsResponse) -> CurveAsOf:
    return CurveAsOf(
        curve_id=body.data.curve_id,
        valid_date=body.data.valid_date,
        as_of=body.meta.as_of,
        points=tuple(
            CurvePoint(maturity=point.maturity, months=point.months, value=point.value)
            for point in body.data.points
        ),
    )


def _problem_detail(response: httpx.Response) -> str:
    """The ``detail`` of a problem document, or the raw body when it is not one."""
    try:
        body: Any = response.json()
    except ValueError:
        return response.text
    detail: object = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    return response.text
