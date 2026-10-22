"""Derived measures of a curve as the access service relays them from processing."""

from dataclasses import dataclass
from datetime import date, datetime

from access.domain.quality import QualityStatus


@dataclass(frozen=True, slots=True)
class MeasureInput:
    maturity: str
    value: float
    version_id: int
    status: QualityStatus


@dataclass(frozen=True, slots=True)
class MeasureQuality:
    status: QualityStatus
    flagged: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MeasurePoint:
    valid_date: date
    spread_2y_10y: float | None
    spread_3m_10y: float | None
    curvature_2y_5y_10y: float | None
    inverted: bool | None
    inputs: tuple[MeasureInput, ...]
    missing: tuple[str, ...]
    quality: MeasureQuality


@dataclass(frozen=True, slots=True)
class CurveMeasures:
    curve_id: str
    valid_from: date
    valid_to: date
    as_of: datetime
    method_version: str
    points: tuple[MeasurePoint, ...]


class MeasuresUnavailableError(Exception):
    """Processing cannot answer a measures read."""


def inputs_are_checked(measures: CurveMeasures) -> bool:
    """True when no input of any point is unchecked; a range without points is checked."""
    return all(
        input_.status != QualityStatus.UNCHECKED
        for point in measures.points
        for input_ in point.inputs
    )
