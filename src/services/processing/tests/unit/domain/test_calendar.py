from datetime import date, timedelta
from pathlib import Path

import pytest

from processing.domain.calendar import (
    TARGET,
    US_BOND_MARKET,
    BusinessCalendar,
    is_target_business_day,
    is_us_bond_market_business_day,
)

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
    days = TARGET.business_days(start, end)

    assert date(2026, 4, 3) not in days
    assert date(2026, 4, 6) not in days
    assert date(2026, 4, 4) not in days
    assert date(2026, 4, 5) not in days
    assert date(2026, 4, 2) in days
    assert date(2026, 4, 7) in days


def test_the_target_calendar_is_named_target() -> None:
    assert TARGET.name == "TARGET"
    assert TARGET.is_business_day is is_target_business_day


def test_a_calendar_lists_the_days_its_rule_accepts() -> None:
    mondays = BusinessCalendar("Mondays", lambda day: day.weekday() == 0)

    assert mondays.business_days(date(2026, 10, 5), date(2026, 10, 18)) == [
        date(2026, 10, 5),
        date(2026, 10, 12),
    ]


def test_an_inverted_range_has_no_business_days() -> None:
    assert TARGET.business_days(date(2026, 10, 8), date(2026, 10, 7)) == []


US_CLOSED_WEEKDAYS_FIXTURE = Path(__file__).parents[2] / "fixtures" / "ust_closed_weekdays.txt"


def _recorded_closed_weekdays() -> dict[int, set[date]]:
    """The weekdays without a Treasury curve per year, from the recorded history."""
    closed: dict[int, set[date]] = {}
    for line in US_CLOSED_WEEKDAYS_FIXTURE.read_text().splitlines():
        if line.startswith("#"):
            continue
        year_text, _, days = line.partition(": ")
        closed[int(year_text)] = {
            date(int(year_text), *map(int, day.split("-"))) for day in days.split()
        }
    return closed


@pytest.mark.parametrize(
    ("year", "closed"),
    sorted(_recorded_closed_weekdays().items()),
    ids=lambda value: str(value) if isinstance(value, int) else "",
)
def test_the_us_calendar_matches_the_recorded_publication_days(
    year: int, closed: set[date]
) -> None:
    """The Treasury published on every other weekday of ``year`` (see the fixture's header)."""
    business = set(US_BOND_MARKET.business_days(date(year, 1, 1), date(year, 12, 31)))
    assert {day for day in _all_weekdays(year) if day not in business} == closed


def _all_weekdays(year: int) -> list[date]:
    days = []
    day = date(year, 1, 1)
    while day.year == year:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


@pytest.mark.parametrize(
    "day",
    [
        date(2025, 4, 18),  # Good Friday
        date(2025, 1, 1),  # New Year's Day
        date(2024, 6, 19),  # Juneteenth
        date(2024, 7, 4),  # Independence Day
        date(2018, 12, 5),  # national day of mourning (George H. W. Bush)
        date(2026, 7, 3),  # Independence Day observed on the Friday before a Saturday
        date(2026, 12, 25),
    ],
)
def test_us_bond_market_holidays_are_not_business_days(day: date) -> None:
    assert not is_us_bond_market_business_day(day)


@pytest.mark.parametrize(
    "day",
    [
        date(2021, 6, 18),  # Juneteenth was not a bond market holiday before 2022
        date(2021, 12, 31),  # New Year's Day on a Saturday: the Treasury published
        date(2023, 11, 10),  # Veterans Day on a Saturday: the Treasury published
        date(2026, 4, 3),  # Good Friday in an early-close year: the Treasury published
        date(2025, 1, 9),  # national day of mourning (Jimmy Carter): a trading day
    ],
)
def test_us_bond_market_days_the_treasury_published_are_business_days(day: date) -> None:
    assert is_us_bond_market_business_day(day)


def test_the_us_bond_market_calendar_is_named_and_uses_the_rules() -> None:
    assert US_BOND_MARKET.name == "US bond market"
    assert US_BOND_MARKET.is_business_day is is_us_bond_market_business_day
    assert US_BOND_MARKET.business_days(date(2025, 4, 17), date(2025, 4, 21)) == [
        date(2025, 4, 17),
        date(2025, 4, 21),
    ]
