"""Business-day calendars for completeness checks.

TARGET follows the same rules as orchestration. The US bond market calendar is the one of the
Treasury par yield curve (see ``us_calendar`` in orchestration, which follows the same rules).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

from dateutil.easter import easter

MONDAY = 0
THURSDAY = 3
SATURDAY = 5
SUNDAY = 6
FIXED_HOLIDAYS = frozenset({(1, 1), (5, 1), (12, 25), (12, 26)})

# Fixed-date US holidays the bond market observes on the Friday before when they fall on a
# Saturday. Every fixed holiday moves from Sunday to Monday; New Year's Day and Veterans Day do
# not move to the Friday, because the Treasury published on those Fridays.
US_FRIDAY_BEFORE_SATURDAY_HOLIDAYS = frozenset({(7, 4), (12, 25), (6, 19)})
# Unscheduled closures on which the Treasury published nothing: 1994 and 2001 events, the 2004 and
# 2018 national days of mourning, and Hurricane Sandy. Found in the Treasury history 1990 to 2026.
# The 2007 and 2025 days of mourning were trading days.
US_EXTRA_CLOSURES = frozenset(
    {
        date(1994, 4, 27),
        date(2001, 9, 11),
        date(2001, 9, 12),
        date(2004, 6, 11),
        date(2012, 10, 30),
        date(2018, 12, 5),
    }
)
# Good Fridays on which the Treasury published (early-close years, when the jobs report came out).
# Good Friday is otherwise a closure.
US_OPEN_GOOD_FRIDAYS = frozenset(
    {
        date(1996, 4, 5),
        date(1999, 4, 2),
        date(2007, 4, 6),
        date(2010, 4, 2),
        date(2012, 4, 6),
        date(2015, 4, 3),
        date(2021, 4, 2),
        date(2023, 4, 7),
        date(2026, 4, 3),
    }
)


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


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    following = date(year + (month == 12), month % 12 + 1, 1)
    last = following - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed_fixed_holiday(year: int, month: int, day: int) -> date | None:
    """The weekday a fixed-date holiday is observed on; None if the market does not observe it."""
    holiday = date(year, month, day)
    if holiday.weekday() == SUNDAY:
        return holiday + timedelta(days=1)
    if holiday.weekday() == SATURDAY and (month, day) in US_FRIDAY_BEFORE_SATURDAY_HOLIDAYS:
        return holiday - timedelta(days=1)
    return None if holiday.weekday() == SATURDAY else holiday


@cache
def us_bond_market_holidays(year: int) -> frozenset[date]:
    """The rule-based closures of ``year``, before the extra closures and open Good Fridays."""
    fixed = [(1, 1), (7, 4), (11, 11), (12, 25)]
    if year >= 2022:
        fixed.append((6, 19))  # Juneteenth, a bond market holiday since 2022
    observed = {_observed_fixed_holiday(year, month, day) for month, day in fixed}
    moving = {
        _nth_weekday(year, 1, MONDAY, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, MONDAY, 3),  # Presidents' Day
        _last_weekday(year, 5, MONDAY),  # Memorial Day
        _nth_weekday(year, 9, MONDAY, 1),  # Labor Day
        _nth_weekday(year, 10, MONDAY, 2),  # Columbus Day
        _nth_weekday(year, 11, THURSDAY, 4),  # Thanksgiving Day
        easter(year) - timedelta(days=2),  # Good Friday
    }
    return frozenset(day for day in observed | moving if day is not None)


def is_us_bond_market_business_day(day: date) -> bool:
    """Whether the US bond market is open, and the Treasury publishes its curve, on ``day``."""
    if day.weekday() >= SATURDAY:
        return False
    if day in US_OPEN_GOOD_FRIDAYS:
        return True
    if day in US_EXTRA_CLOSURES:
        return False
    return day not in us_bond_market_holidays(day.year)


US_BOND_MARKET = BusinessCalendar(
    name="US bond market", is_business_day=is_us_bond_market_business_day
)
