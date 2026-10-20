"""A published curve as the access service reads it, and the errors of reading it."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """One maturity; ``value`` is None when no published value was known as of the read."""

    maturity: str
    months: int
    value: float | None
    version_id: int | None


@dataclass(frozen=True, slots=True)
class CurveAsOf:
    """One curve on one valid date, as it was known at ``as_of``."""

    curve_id: str
    valid_date: date
    as_of: datetime
    points: tuple[CurvePoint, ...]


class CurveNotFoundError(Exception):
    """The curve is unknown to the curve store."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidCurveQueryError(Exception):
    """The curve store rejected the query (for example a malformed parameter)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PersistenceUnavailableError(Exception):
    """The curve store could not answer."""
