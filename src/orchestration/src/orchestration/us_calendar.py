"""The US bond market calendar: the days on which the Treasury publishes its par yield curve.

The bond market is closed on weekends, on the federal holidays it observes (Good Friday included,
and Juneteenth since 2022), and on a few unscheduled closures. Fridays before a Saturday
holiday are closed only for Independence Day and Christmas. The schedules use it to know when
the Treasury has published, not to judge data quality: processing has the same rules for its
completeness checks, and tests them against the recorded publication days.
"""

from datetime import date, timedelta
from functools import cache

from dateutil.easter import easter

MONDAY = 0
THURSDAY = 3
SATURDAY = 5
SUNDAY = 6
FRIDAY_BEFORE_SATURDAY_HOLIDAYS = frozenset({(7, 4), (12, 25), (6, 19)})
EXTRA_CLOSURES = frozenset(
    {
        date(1994, 4, 27),
        date(2001, 9, 11),
        date(2001, 9, 12),
        date(2004, 6, 11),
        date(2012, 10, 30),
        date(2018, 12, 5),
    }
)
OPEN_GOOD_FRIDAYS = frozenset(
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


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    following = date(year + (month == 12), month % 12 + 1, 1)
    last = following - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed_fixed_holiday(year: int, month: int, day: int) -> date | None:
    holiday = date(year, month, day)
    if holiday.weekday() == SUNDAY:
        return holiday + timedelta(days=1)
    if holiday.weekday() == SATURDAY:
        return (
            holiday - timedelta(days=1) if (month, day) in FRIDAY_BEFORE_SATURDAY_HOLIDAYS else None
        )
    return holiday


@cache
def us_bond_market_holidays(year: int) -> frozenset[date]:
    """The rule-based closures of ``year``, before the extra closures and open Good Fridays."""
    fixed = [(1, 1), (7, 4), (11, 11), (12, 25)]
    if year >= 2022:
        fixed.append((6, 19))
    observed = {_observed_fixed_holiday(year, month, day) for month, day in fixed}
    moving = {
        _nth_weekday(year, 1, MONDAY, 3),
        _nth_weekday(year, 2, MONDAY, 3),
        _last_weekday(year, 5, MONDAY),
        _nth_weekday(year, 9, MONDAY, 1),
        _nth_weekday(year, 10, MONDAY, 2),
        _nth_weekday(year, 11, THURSDAY, 4),
        easter(year) - timedelta(days=2),
    }
    return frozenset(day for day in observed | moving if day is not None)


def is_us_business_day(day: date) -> bool:
    """Whether the US bond market is open, and the Treasury publishes its curve, on ``day``."""
    if day.weekday() >= SATURDAY:
        return False
    if day in OPEN_GOOD_FRIDAYS:
        return True
    if day in EXTRA_CLOSURES:
        return False
    return day not in us_bond_market_holidays(day.year)
