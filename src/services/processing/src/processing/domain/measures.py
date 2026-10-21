"""Derived measures of a curve on one valid date: spreads, curvature and inversion. No I/O."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from processing.domain.quality import Status

METHOD_VERSION = "1"
INPUT_MATURITIES: tuple[str, ...] = ("3M", "2Y", "5Y", "10Y")
MAX_MEASURES_RANGE = timedelta(days=3660)
BASIS_POINTS_PER_PERCENT = Decimal(100)

_STATUS_RANK: dict[Status, int] = {
    Status.WARN: 3,
    Status.INFO: 2,
    Status.UNCHECKED: 1,
    Status.PASSED: 0,
}


@dataclass(frozen=True, slots=True)
class MeasureInput:
    maturity: str
    value: Decimal
    version_id: int
    status: Status


@dataclass(frozen=True, slots=True)
class MeasureQuality:
    status: Status
    flagged: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MeasurePoint:
    valid_date: date
    spread_2y_10y: Decimal | None
    spread_3m_10y: Decimal | None
    curvature_2y_5y_10y: Decimal | None
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


def worst_input_status(statuses: Iterable[Status]) -> Status:
    """Worst status by rank WARN > INFO > UNCHECKED > PASSED; an empty input is PASSED."""
    return max(statuses, key=_STATUS_RANK.__getitem__, default=Status.PASSED)


def _spread(later: Decimal, earlier: Decimal) -> Decimal:
    return (later - earlier) * BASIS_POINTS_PER_PERCENT


def measure_point(valid_date: date, inputs: Mapping[str, MeasureInput]) -> MeasurePoint:
    present = [inputs[m] for m in INPUT_MATURITIES if m in inputs]
    missing = tuple(m for m in INPUT_MATURITIES if m not in inputs)
    y3m = inputs["3M"].value if "3M" in inputs else None
    y2y = inputs["2Y"].value if "2Y" in inputs else None
    y5y = inputs["5Y"].value if "5Y" in inputs else None
    y10y = inputs["10Y"].value if "10Y" in inputs else None

    spread_2y_10y: Decimal | None = None
    if y2y is not None and y10y is not None:
        spread_2y_10y = _spread(y10y, y2y)
    spread_3m_10y: Decimal | None = None
    if y3m is not None and y10y is not None:
        spread_3m_10y = _spread(y10y, y3m)
    curvature: Decimal | None = None
    if y2y is not None and y5y is not None and y10y is not None:
        curvature = (2 * y5y - y2y - y10y) * BASIS_POINTS_PER_PERCENT
    inverted = spread_2y_10y < 0 if spread_2y_10y is not None else None

    quality = MeasureQuality(
        status=worst_input_status(i.status for i in present),
        flagged=tuple(i.maturity for i in present if i.status in (Status.WARN, Status.INFO)),
    )
    return MeasurePoint(
        valid_date=valid_date,
        spread_2y_10y=spread_2y_10y,
        spread_3m_10y=spread_3m_10y,
        curvature_2y_5y_10y=curvature,
        inverted=inverted,
        inputs=tuple(present),
        missing=missing,
        quality=quality,
    )
