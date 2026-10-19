"""A published series of one maturity as the access service reads it."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """One valid date with a published value known as of ``as_of``."""

    valid_date: date
    value: float


@dataclass(frozen=True, slots=True)
class Series:
    """One maturity of a curve over valid dates, as it was known at ``as_of``."""

    curve_id: str
    maturity: str
    as_of: datetime
    points: tuple[SeriesPoint, ...]
