"""Client of the persistence service for quality checks (grid and series reads)."""

from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx
from contracts.persistence import v1
from pydantic import ValidationError

from processing.application.ports import Grid
from processing.domain.quality import Value


class PersistenceReadError(RuntimeError):
    """Persistence answered with an unexpected status or an invalid body."""


class PersistenceClient:
    """Reads curve grids and maturity series as of a knowledge time."""

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

    async def grid(self, curve_id: str) -> Grid | None:
        """Latest curve grid and persistence knowledge time; ``None`` when the curve is unknown."""
        path = v1.CURVE_OBSERVATIONS_PATH.format(curve_id=quote(curve_id, safe=""))
        try:
            response = await self._http.get(path)
        except httpx.HTTPError as error:
            raise PersistenceReadError from error

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code != httpx.codes.OK:
            raise PersistenceReadError(f"persistence answered {response.status_code}")

        body = _parse_curve(response)
        maturities = tuple(point.maturity for point in body.data.points)
        return Grid(maturities=maturities, as_of=body.meta.as_of)

    async def series(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
    ) -> list[Value]:
        """One maturity between two valid dates; an unknown series is empty."""
        path = v1.SERIES_OBSERVATIONS_PATH.format(
            curve_id=quote(curve_id, safe=""), maturity=quote(maturity, safe="")
        )
        params = {
            "from": valid_from.isoformat(),
            "to": valid_to.isoformat(),
            "as_of": as_of.isoformat(),
        }
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise PersistenceReadError from error

        if response.status_code == httpx.codes.NOT_FOUND:
            return []
        if response.status_code != httpx.codes.OK:
            raise PersistenceReadError(f"persistence answered {response.status_code}")

        body = _parse_series(response)
        return [
            Value(
                version_id=point.version_id,
                maturity=maturity,
                valid_date=point.valid_date,
                value=Decimal(str(point.value)),
            )
            for point in body.data.points
        ]


def _parse_curve(response: httpx.Response) -> v1.CurveObservationsResponse:
    try:
        return v1.CurveObservationsResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise PersistenceReadError("persistence sent an unexpected curve body") from error


def _parse_series(response: httpx.Response) -> v1.SeriesObservationsResponse:
    try:
        return v1.SeriesObservationsResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise PersistenceReadError("persistence sent an unexpected series body") from error
