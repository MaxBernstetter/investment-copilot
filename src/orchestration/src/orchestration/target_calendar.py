"""The TARGET calendar: the days on which the ECB publishes and TARGET2 settles.

TARGET is closed on weekends, New Year's Day, Good Friday, Easter Monday, Labour Day
(1 May), Christmas Day and 26 December. This fixed set applies since 2002. The
schedules use it to know when a source has published, not to judge data quality
(market calendars for completeness checks belong to processing).
"""

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


def previous_target_business_day(day: date) -> date:
    """The last TARGET business day strictly before ``day``."""
    previous = day - timedelta(days=1)
    while not is_target_business_day(previous):
        previous -= timedelta(days=1)
    return previous
