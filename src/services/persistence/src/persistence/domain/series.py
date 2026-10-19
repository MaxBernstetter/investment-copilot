"""A published series of one maturity as it was known at a knowledge time.

A point is one valid date with a published value known at that time; valid
dates without one are left out, so a series can have gaps.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    valid_date: date
    value: float


@dataclass(frozen=True, slots=True)
class Series:
    curve_id: str
    maturity: str
    as_of: datetime
    points: tuple[SeriesPoint, ...]


class InvalidRangeError(ValueError):
    """The requested valid-date range is reversed or longer than the service serves."""
