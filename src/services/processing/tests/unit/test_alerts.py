from datetime import UTC, datetime

from processing.application.alerts import LatestCheckRun, quality_warn_active

RECORDED_AT = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)


def test_quality_warn_is_active_with_a_warn_day() -> None:
    run = LatestCheckRun(curve_id="ecb-aaa-spot-sim", recorded_at=RECORDED_AT, warn_days=2)

    assert quality_warn_active(run) is True


def test_quality_warn_is_inactive_without_one() -> None:
    run = LatestCheckRun(curve_id="ecb-aaa-spot-sim", recorded_at=RECORDED_AT, warn_days=0)

    assert quality_warn_active(run) is False
