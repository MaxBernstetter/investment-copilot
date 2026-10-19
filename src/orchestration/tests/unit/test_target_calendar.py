from datetime import date

import pytest

from orchestration.target_calendar import is_target_business_day, previous_target_business_day

# TARGET closing days 2026, as published by the ECB (weekends aside).
TARGET_HOLIDAYS_2026 = [
    date(2026, 1, 1),  # New Year's Day
    date(2026, 4, 3),  # Good Friday
    date(2026, 4, 6),  # Easter Monday
    date(2026, 5, 1),  # Labour Day
    date(2026, 12, 25),  # Christmas Day
    date(2026, 12, 26),  # Boxing Day (a Saturday in 2026)
]


@pytest.mark.parametrize("day", TARGET_HOLIDAYS_2026)
def test_target_holidays_are_no_business_days(day: date) -> None:
    assert not is_target_business_day(day)


@pytest.mark.parametrize(
    "day",
    [date(2027, 3, 26), date(2027, 3, 29), date(2025, 4, 18), date(2025, 4, 21)],
    ids=["good-friday-2027", "easter-monday-2027", "good-friday-2025", "easter-monday-2025"],
)
def test_easter_holidays_move_with_easter(day: date) -> None:
    assert not is_target_business_day(day)


@pytest.mark.parametrize("day", [date(2026, 10, 17), date(2026, 10, 18)], ids=["sat", "sun"])
def test_weekends_are_no_business_days(day: date) -> None:
    assert not is_target_business_day(day)


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 10, 16),
        date(2026, 4, 2),
        date(2026, 4, 7),
        date(2026, 12, 24),
        date(2026, 12, 31),
    ],
    ids=["friday", "maundy-thursday", "easter-tuesday", "christmas-eve", "new-years-eve"],
)
def test_other_weekdays_are_business_days(day: date) -> None:
    assert is_target_business_day(day)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 10, 14), date(2026, 10, 13)),  # Wednesday -> Tuesday
        (date(2026, 10, 19), date(2026, 10, 16)),  # Monday -> Friday
        (date(2026, 4, 7), date(2026, 4, 2)),  # after Easter -> Maundy Thursday
        (date(2026, 5, 4), date(2026, 4, 30)),  # after Labour Day -> Thursday
        (date(2026, 12, 28), date(2026, 12, 24)),  # after Christmas -> Christmas Eve
        (date(2027, 1, 4), date(2026, 12, 31)),  # across the year end
    ],
)
def test_previous_target_business_day_skips_weekends_and_holidays(
    day: date, expected: date
) -> None:
    assert previous_target_business_day(day) == expected
