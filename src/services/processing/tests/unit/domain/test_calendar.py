from datetime import date

import pytest

from processing.domain.calendar import is_target_business_day, target_business_days

TARGET_HOLIDAYS_2026 = [
    date(2026, 4, 3),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 12, 25),
    date(2026, 12, 26),
]


@pytest.mark.parametrize("day", TARGET_HOLIDAYS_2026)
def test_target_holidays_are_not_business_days(day: date) -> None:
    assert not is_target_business_day(day)


@pytest.mark.parametrize("day", [date(2026, 10, 17), date(2026, 10, 18)], ids=["sat", "sun"])
def test_weekends_are_not_business_days(day: date) -> None:
    assert not is_target_business_day(day)


def test_a_normal_weekday_is_a_business_day() -> None:
    assert is_target_business_day(date(2026, 10, 7))


def test_target_business_days_excludes_holidays_and_weekends() -> None:
    start = date(2026, 4, 1)
    end = date(2026, 4, 10)
    days = target_business_days(start, end)

    assert date(2026, 4, 3) not in days
    assert date(2026, 4, 6) not in days
    assert date(2026, 4, 4) not in days
    assert date(2026, 4, 5) not in days
    assert date(2026, 4, 2) in days
    assert date(2026, 4, 7) in days
