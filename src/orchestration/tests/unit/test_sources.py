from datetime import date, datetime

from orchestration.sources import BERLIN, ECB, SOURCES


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
