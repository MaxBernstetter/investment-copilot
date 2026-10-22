"""Use case: derived measures of a curve as known at a time."""

from collections import defaultdict
from datetime import date, datetime
from typing import Protocol

from processing.application.check_quality import UnknownCurveError
from processing.application.knowledge_time import resolve_as_of
from processing.application.ports import ObservationReader
from processing.domain.assessment import ValueStatus
from processing.domain.measures import (
    INPUT_MATURITIES,
    MAX_MEASURES_RANGE,
    METHOD_VERSION,
    CurveMeasures,
    MeasureInput,
    measure_point,
)
from processing.domain.quality import Status
from processing.domain.read import InvalidRangeError
from processing.domain.rule_config import RULES_BY_CURVE


class MeasureQualityReader(Protocol):
    async def current_time(self) -> datetime:
        """The database clock now, in UTC."""

    async def value_statuses(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[ValueStatus]:
        """Latest value quality per published value known at ``as_of``."""


class GetMeasures:
    def __init__(self, observations: ObservationReader, quality: MeasureQualityReader) -> None:
        self._observations = observations
        self._quality = quality

    async def __call__(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> CurveMeasures:
        if curve_id not in RULES_BY_CURVE:
            raise UnknownCurveError(curve_id)
        if as_of is not None:
            await resolve_as_of(self._quality, as_of)
        if valid_from > valid_to:
            raise InvalidRangeError(f"from {valid_from} is after to {valid_to}")
        if valid_to - valid_from > MAX_MEASURES_RANGE:
            raise InvalidRangeError(f"the range exceeds {MAX_MEASURES_RANGE.days} days")

        grid = await self._observations.grid(curve_id)
        if grid is None:
            raise UnknownCurveError(curve_id)
        # Inputs and their quality are read at one effective knowledge time, capped at the horizon.
        effective = grid.as_of if as_of is None else min(as_of, grid.as_of)

        inputs_by_date: dict[date, dict[str, MeasureInput]] = defaultdict(dict)
        for maturity in INPUT_MATURITIES:
            values = await self._observations.series(
                curve_id, maturity, valid_from, valid_to, effective
            )
            statuses = await self._quality.value_statuses(
                curve_id, valid_from, valid_to, effective, maturity=maturity
            )
            status_by_key = {
                (status.version_id, status.maturity, status.valid_date): status.status
                for status in statuses
            }
            for value in values:
                key = (value.version_id, value.maturity, value.valid_date)
                inputs_by_date[value.valid_date][maturity] = MeasureInput(
                    maturity=value.maturity,
                    value=value.value,
                    version_id=value.version_id,
                    status=status_by_key.get(key, Status.UNCHECKED),
                )

        points = tuple(
            measure_point(valid_date, inputs_by_date[valid_date])
            for valid_date in sorted(inputs_by_date)
        )
        return CurveMeasures(
            curve_id=curve_id,
            valid_from=valid_from,
            valid_to=valid_to,
            as_of=effective,
            method_version=METHOD_VERSION,
            points=points,
        )
