from datetime import date

import pytest

from ingestion.domain.windows import DateWindow, lookback_window, yearly_windows


def test_lookback_counts_business_days_and_skips_weekends() -> None:
    # Thursday 2026-10-15 minus 10 business days is Thursday 2026-10-01.
    assert lookback_window(date(2026, 10, 15), 10) == DateWindow(
        date(2026, 10, 1), date(2026, 10, 15)
    )


def test_lookback_from_a_monday_reaches_back_over_the_weekend() -> None:
    assert lookback_window(date(2026, 10, 12), 1) == DateWindow(
        date(2026, 10, 9), date(2026, 10, 12)
    )


def test_zero_lookback_is_the_valid_date_only() -> None:
    assert lookback_window(date(2026, 10, 15), 0) == DateWindow(
        date(2026, 10, 15), date(2026, 10, 15)
    )


def test_negative_lookback_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        lookback_window(date(2026, 10, 15), -1)


def test_a_window_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="after its end"):
        DateWindow(date(2026, 10, 2), date(2026, 10, 1))


def test_history_is_split_into_calendar_years_clipped_to_the_range() -> None:
    assert yearly_windows(DateWindow(date(2024, 3, 15), date(2026, 2, 1))) == [
        DateWindow(date(2024, 3, 15), date(2024, 12, 31)),
        DateWindow(date(2025, 1, 1), date(2025, 12, 31)),
        DateWindow(date(2026, 1, 1), date(2026, 2, 1)),
    ]


def test_the_full_ecb_history_takes_23_requests() -> None:
    windows = yearly_windows(DateWindow(date(2004, 9, 6), date(2026, 10, 16)))

    assert len(windows) == 23
    assert windows[0] == DateWindow(date(2004, 9, 6), date(2004, 12, 31))
    assert windows[-1] == DateWindow(date(2026, 1, 1), date(2026, 10, 16))


def test_a_range_within_one_year_is_one_window() -> None:
    window = DateWindow(date(2026, 10, 1), date(2026, 10, 15))

    assert yearly_windows(window) == [window]
