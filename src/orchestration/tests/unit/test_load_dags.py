from datetime import date

from orchestration.ecb_backfill import backfill_years
from orchestration.load_dags import (
    backfill_check_run_id,
    backfill_run_id,
    daily_check_run_id,
    daily_run_id,
)


def test_run_ids_are_unchanged_for_ecb() -> None:
    assert daily_run_id("daily_load_ecb", date(2026, 10, 15)) == "daily_load_ecb-2026-10-15"
    assert (
        daily_check_run_id("daily_load_ecb", "ecb-aaa-spot", date(2026, 10, 15))
        == "daily_load_ecb-check-ecb-aaa-spot-2026-10-15"
    )
    assert (
        backfill_run_id("backfill_ecb", date(2004, 1, 1), date(2004, 12, 31))
        == "backfill_ecb-2004-01-01-2004-12-31"
    )
    assert (
        backfill_check_run_id("backfill_ecb", "ecb-all-spot", date(2004, 1, 1), date(2004, 12, 31))
        == "backfill_ecb-check-ecb-all-spot-2004-01-01-2004-12-31"
    )


def test_run_ids_carry_the_dag_id_of_another_source() -> None:
    assert daily_run_id("daily_load_ust", date(2026, 10, 15)) == "daily_load_ust-2026-10-15"
    assert (
        backfill_check_run_id("backfill_ust", "ust-par", date(2004, 1, 1), date(2004, 12, 31))
        == "backfill_ust-check-ust-par-2004-01-01-2004-12-31"
    )


def test_the_ust_backfill_from_1990_is_one_request_per_year() -> None:
    chunks = backfill_years(date(1990, 1, 1), date(2026, 10, 23))

    assert len(chunks) == 37
    assert chunks[0] == (date(1990, 1, 1), date(1990, 12, 31))
    assert chunks[-1] == (date(2026, 1, 1), date(2026, 10, 23))
