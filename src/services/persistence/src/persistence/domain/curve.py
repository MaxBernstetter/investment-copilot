"""A published curve as it was known at a knowledge time.

A point is one maturity of the curve's grid; its value is None where no
published value was known at that time.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class CurvePoint:
    maturity: str
    months: float
    value: float | None
    version_id: int | None


@dataclass(frozen=True, slots=True)
class CurveAsOf:
    curve_id: str
    valid_date: date
    as_of: datetime
    points: tuple[CurvePoint, ...]


class NothingKnownError(LookupError):
    """No published value of the curve is known at the requested time."""


class FutureAsOfError(ValueError):
    """The requested knowledge time lies after the database clock."""
