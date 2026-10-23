from datetime import date

import pytest

from orchestration.us_calendar import is_us_business_day

# Treasury publication days checked against the recorded history (1990 to 2026): closures of
# bond market holidays, the Good Friday closures and openings, and the unscheduled closures.
US_CLOSED_WEEKDAYS = [
    date(2018, 1, 15),  # Martin Luther King Jr. Day
    date(2018, 3, 30),  # Good Friday
    date(2018, 5, 28),  # Memorial Day
    date(2018, 12, 5),  # national day of mourning (George H. W. Bush)
    date(2018, 12, 25),
    date(2025, 1, 1),
    date(2025, 4, 18),  # Good Friday
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),
    date(2025, 11, 27),  # Thanksgiving Day
    date(2026, 7, 3),  # Independence Day observed on the Friday before a Saturday
    date(2001, 9, 11),  # terrorist attacks: the bond market closed
    date(2012, 10, 30),  # Hurricane Sandy
    date(2020, 7, 3),  # Independence Day observed on the Friday before a Saturday
    date(2021, 12, 24),  # Christmas observed on the Friday before a Saturday
    date(2022, 6, 20),  # Juneteenth observed on the Monday after a Sunday
]
US_OPEN_WEEKDAYS = [
    date(2021, 12, 31),  # New Year's Day on a Saturday: the Treasury published
    date(2023, 11, 10),  # Veterans Day on a Saturday: the Treasury published
    date(2026, 4, 3),  # Good Friday in an early-close year: the Treasury published
    date(2025, 1, 9),  # national day of mourning (Jimmy Carter): a trading day
    date(2025, 10, 10),  # a plain Friday
    date(2021, 6, 18),  # Juneteenth was not a bond market holiday before 2022
]


@pytest.mark.parametrize("day", US_CLOSED_WEEKDAYS)
def test_the_us_closures_are_not_business_days(day: date) -> None:
    assert not is_us_business_day(day)


@pytest.mark.parametrize("day", US_OPEN_WEEKDAYS)
def test_the_us_openings_are_business_days(day: date) -> None:
    assert is_us_business_day(day)


@pytest.mark.parametrize("day", [date(2026, 10, 24), date(2026, 10, 25)], ids=["sat", "sun"])
def test_weekends_are_not_business_days(day: date) -> None:
    assert not is_us_business_day(day)
