from datetime import date

import pytest

from orchestration.ecb_backfill import backfill_years, history_command


def test_splits_a_range_into_calendar_years() -> None:
    assert backfill_years(date(2004, 9, 6), date(2006, 3, 1)) == [
        (date(2004, 9, 6), date(2004, 12, 31)),
        (date(2005, 1, 1), date(2005, 12, 31)),
        (date(2006, 1, 1), date(2006, 3, 1)),
    ]


def test_a_range_within_one_year_is_one_chunk() -> None:
    assert backfill_years(date(2024, 3, 4), date(2024, 3, 8)) == [
        (date(2024, 3, 4), date(2024, 3, 8))
    ]


def test_rejects_start_after_end() -> None:
    with pytest.raises(ValueError, match="after end"):
        backfill_years(date(2024, 3, 8), date(2024, 3, 4))


def test_history_command_argv() -> None:
    assert history_command("ecb", date(2004, 9, 6), date(2004, 12, 31), "backfill_ecb-x") == [
        "ingestion-load-ecb",
        "history",
        "--start",
        "2004-09-06",
        "--end",
        "2004-12-31",
        "--run-id",
        "backfill_ecb-x",
    ]


def test_history_command_names_the_source() -> None:
    assert history_command("ust", date(2004, 9, 6), date(2004, 12, 31), "backfill_ust-x")[0] == (
        "ingestion-load-ust"
    )
