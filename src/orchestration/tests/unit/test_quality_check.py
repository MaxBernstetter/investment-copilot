from datetime import date

from orchestration.quality_check import (
    ECB_CURVE_ID,
    JOB_COMMAND,
    daily_check_command,
    range_check_command,
)


def test_the_daily_check_covers_three_weeks_up_to_the_valid_date() -> None:
    valid_date = date(2026, 10, 16)
    assert daily_check_command(valid_date, "daily_load_ecb-check-2026-10-16") == [
        JOB_COMMAND,
        ECB_CURVE_ID,
        "--from",
        "2026-09-25",
        "--to",
        "2026-10-16",
        "--run-id",
        "daily_load_ecb-check-2026-10-16",
    ]


def test_the_range_check_command_argv() -> None:
    assert range_check_command(date(2004, 9, 6), date(2004, 12, 31), "backfill_ecb-check-x") == [
        JOB_COMMAND,
        ECB_CURVE_ID,
        "--from",
        "2004-09-06",
        "--to",
        "2004-12-31",
        "--run-id",
        "backfill_ecb-check-x",
    ]
