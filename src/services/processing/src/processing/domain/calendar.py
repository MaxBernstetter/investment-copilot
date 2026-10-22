"""Business-day calendars for completeness checks.

TARGET follows the same rules as orchestration.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.easter import easter

SATURDAY = 5
FIXED_HOLIDAYS = frozenset({(1, 1), (5, 1), (12, 25), (12, 26)})


def is_target_business_day(day: date) -> bool:
    """Whether TARGET is open on ``day``."""
    if day.weekday() >= SATURDAY or (day.month, day.day) in FIXED_HOLIDAYS:
        return False
    easter_sunday = easter(day.year)
    return day not in (easter_sunday - timedelta(days=2), easter_sunday + timedelta(days=1))


@dataclass(frozen=True, slots=True)
class BusinessCalendar:
    """A named business-day calendar; its days are the ones completeness expects values on."""

    name: str
    is_business_day: Callable[[date], bool]

    def business_days(self, start: date, end: date) -> list[date]:
        """Every business day from ``start`` through ``end``, inclusive (empty if start > end)."""
        if start > end:
            return []
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_business_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days


TARGET = BusinessCalendar(name="TARGET", is_business_day=is_target_business_day)
