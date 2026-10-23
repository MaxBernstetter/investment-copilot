from datetime import date, datetime

import pytest

from orchestration.sources import BERLIN, ECB, SOURCES, UST, LoadSource


def test_ecb_config_literals() -> None:
    assert ECB.source_id == "ecb"
    assert ECB.pool == "ecb"
    assert ECB.job_command == "ingestion-load-ecb"
    assert ECB.cron == "15 13 * * 1-5"
    assert ECB.timezone == "Europe/Berlin"
    assert ECB.start_date == datetime(2026, 10, 19, tzinfo=BERLIN)
    assert ECB.start_date.date() == date(2026, 10, 19)
    assert ECB.curve_ids == ("ecb-aaa-spot", "ecb-all-spot")


def test_source_ids_are_unique_and_identifier_like() -> None:
    ids = [source.source_id for source in SOURCES]

    assert len(ids) == len(set(ids))
    assert all(source_id.isidentifier() for source_id in ids)


def test_ust_config_literals() -> None:
    assert UST.source_id == "ust"
    assert UST.pool == "ust"
    assert UST.job_command == "ingestion-load-ust"
    assert UST.cron == "0 8 * * 2-6"
    assert UST.timezone == "Europe/Berlin"
    assert UST.start_date == datetime(2026, 10, 27, tzinfo=BERLIN)
    assert UST.curve_ids == ("ust-par",)


@pytest.mark.parametrize(
    ("run_day", "loads", "publishes"),
    [
        (date(2026, 10, 27), date(2026, 10, 26), True),  # Tuesday loads Monday
        (date(2026, 10, 31), date(2026, 10, 30), True),  # Saturday loads Friday
        (date(2026, 5, 26), date(2026, 5, 25), False),  # Tuesday after Memorial Day: skipped
        (date(2025, 4, 19), date(2025, 4, 18), False),  # Saturday after Good Friday: skipped
        (date(2026, 4, 4), date(2026, 4, 3), True),  # Saturday after an early-close Good Friday
    ],
)
def test_a_ust_run_loads_the_previous_day_when_the_treasury_published_it(
    run_day: date, loads: date, publishes: bool
) -> None:
    assert UST.is_publication_day(run_day) is publishes
    if publishes:
        assert UST.previous_publication_day(run_day) == loads


def test_the_ecb_source_is_unchanged_and_ust_follows_it() -> None:
    assert SOURCES == (ECB, UST)
    assert all(isinstance(source, LoadSource) for source in SOURCES)
