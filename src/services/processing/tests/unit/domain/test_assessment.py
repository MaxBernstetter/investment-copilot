from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from processing.domain.assessment import QualityCheck, assess
from processing.domain.calendar import BusinessCalendar
from processing.domain.quality import Rule, Status, Value
from processing.domain.rule_config import ECB_AAA_SPOT_RULES, MaturityPeriod

RUN_ID = "check-quality-ecb-aaa-spot-sim-2026-10-05-2026-10-08"
CURVE_ID = "ecb-aaa-spot-sim"
CHECKED_AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
GRID = ("10Y", "30Y")
OCT_05 = date(2026, 10, 5)
OCT_06 = date(2026, 10, 6)
OCT_07 = date(2026, 10, 7)
OCT_08 = date(2026, 10, 8)


def point(valid_date: date, maturity: str, number: str, version_id: int = 1) -> Value:
    return Value(
        version_id=version_id,
        maturity=maturity,
        valid_date=valid_date,
        value=Decimal(number),
    )


def assess_chunk(
    series: dict[str, list[Value]],
    valid_from: date,
    valid_to: date,
    *,
    grid: tuple[str, ...] = GRID,
) -> QualityCheck:
    return assess(
        run_id=RUN_ID,
        curve_id=CURVE_ID,
        valid_from=valid_from,
        valid_to=valid_to,
        checked_as_of=CHECKED_AS_OF,
        grid=grid,
        series=series,
        rules=replace(ECB_AAA_SPOT_RULES, expected_maturities=(MaturityPeriod(date.min, grid),)),
    )


def test_every_value_in_range_gets_a_status() -> None:
    series = {
        "10Y": [point(OCT_06, "10Y", "2.62", 1), point(OCT_08, "10Y", "2.64", 2)],
        "30Y": [point(OCT_06, "30Y", "2.70", 3), point(OCT_08, "30Y", "2.71", 4)],
    }

    check = assess_chunk(series, OCT_06, OCT_08)

    assert len(check.values) == 4
    assert {value.status for value in check.values} == {Status.PASSED}


def test_lead_in_values_feed_jumps_but_are_not_assessed() -> None:
    series = {
        "10Y": [
            point(OCT_05, "10Y", "2.62", 1),
            point(OCT_08, "10Y", "26.40", 2),
        ],
    }

    check = assess_chunk(series, OCT_08, OCT_08, grid=("10Y",))

    assert len(check.values) == 1
    assert check.values[0].status is Status.WARN
    jump_findings = [finding for finding in check.findings if finding.rule is Rule.JUMP]
    assert len(jump_findings) == 1


def test_value_status_is_the_worst_severity_of_its_findings() -> None:
    series = {
        "10Y": [
            point(OCT_06, "10Y", "2.62", 1),
            point(OCT_08, "10Y", "26.40", 2),
        ],
    }

    check = assess_chunk(series, OCT_06, OCT_08, grid=("10Y",))

    flagged = next(value for value in check.values if value.valid_date == OCT_08)
    assert flagged.status is Status.WARN
    rules = {finding.rule for finding in check.findings if finding.valid_date == OCT_08}
    assert rules == {Rule.RANGE, Rule.JUMP}


def test_day_status_includes_completeness_findings() -> None:
    series = {
        "10Y": [
            point(OCT_06, "10Y", "2.62", 1),
            point(OCT_07, "10Y", "2.63", 5),
            point(OCT_08, "10Y", "2.64", 2),
        ],
        "30Y": [point(OCT_06, "30Y", "2.70", 3), point(OCT_08, "30Y", "2.71", 4)],
    }

    check = assess_chunk(series, OCT_06, OCT_08)

    day_statuses = {day.valid_date: day.status for day in check.days}
    assert day_statuses[OCT_07] is Status.WARN
    missing = [finding for finding in check.findings if finding.valid_date == OCT_07]
    assert {finding.rule for finding in missing} == {Rule.MISSING_MATURITY}


def test_days_follow_the_curve_calendar() -> None:
    mondays = BusinessCalendar("Mondays", lambda day: day.weekday() == 0)
    rules = replace(
        ECB_AAA_SPOT_RULES,
        calendar=mondays,
        expected_maturities=(MaturityPeriod(date.min, GRID),),
    )

    check = assess(
        run_id=RUN_ID,
        curve_id=CURVE_ID,
        valid_from=OCT_05,
        valid_to=OCT_08,
        checked_as_of=CHECKED_AS_OF,
        grid=GRID,
        series={},
        rules=rules,
    )

    assert [day.valid_date for day in check.days] == [OCT_05]
    assert [(finding.rule, finding.valid_date) for finding in check.findings] == [
        (Rule.MISSING_DATE, OCT_05)
    ]
