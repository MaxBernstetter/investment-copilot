"""TARGET business days for completeness checks (same rules as orchestration)."""

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


def target_business_days(start: date, end: date) -> list[date]:
    """Every TARGET business day from ``start`` through ``end``, inclusive."""
    if start > end:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        if is_target_business_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days
