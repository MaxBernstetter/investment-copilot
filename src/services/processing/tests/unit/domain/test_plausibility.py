from datetime import date
from decimal import Decimal

from processing.domain.explanations import JUMP_INFO, JUMP_WARN, RANGE_WARN
from processing.domain.plausibility import check_jumps, check_range
from processing.domain.quality import Finding, Rule, Severity, Value
from processing.domain.rule_config import ECB_AAA_SPOT

MATURITY = "10Y"


def value(valid_date: date, number: str, version_id: int = 1) -> Value:
    return Value(
        version_id=version_id,
        maturity=MATURITY,
        valid_date=valid_date,
        value=Decimal(number),
    )


OCT_06 = date(2026, 10, 6)
OCT_07 = date(2026, 10, 7)
OCT_08 = date(2026, 10, 8)


def test_the_scenario_bad_value_is_a_range_warn() -> None:
    findings = check_range([value(OCT_08, "26.40")], ECB_AAA_SPOT)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule is Rule.RANGE
    assert finding.severity is Severity.WARN
    assert finding.evidence == "26.40 % on 2026-10-08"
    assert finding.explanation == RANGE_WARN
    assert finding.version_id == 1
    assert finding.value == Decimal("26.40")


def test_the_scenario_bad_value_is_a_jump_warn() -> None:
    series = [value(OCT_06, "2.62"), value(OCT_08, "26.40")]

    findings = check_jumps(series, OCT_06, ECB_AAA_SPOT)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule is Rule.JUMP
    assert finding.severity is Severity.WARN
    assert finding.valid_date == OCT_08
    assert finding.evidence == "26.40 % on 2026-10-08 after 2.62 % on 2026-10-06 (+2378.0 bp)"
    assert finding.explanation == JUMP_WARN


def test_the_scenario_correction_passes() -> None:
    series = [value(OCT_06, "2.62"), value(OCT_07, "2.63"), value(OCT_08, "2.64")]

    assert check_range(series, ECB_AAA_SPOT) == []
    assert check_jumps(series, OCT_06, ECB_AAA_SPOT) == []


def test_a_30_bp_move_is_info() -> None:
    series = [value(OCT_06, "2.62"), value(OCT_07, "2.92")]

    findings = check_jumps(series, OCT_06, ECB_AAA_SPOT)

    assert len(findings) == 1
    assert findings[0].severity is Severity.INFO
    assert findings[0].explanation == JUMP_INFO
    assert findings[0].evidence == "2.92 % on 2026-10-07 after 2.62 % on 2026-10-06 (+30.0 bp)"


def test_exactly_25_bp_is_not_flagged_and_exactly_50_bp_is_only_info() -> None:
    at_25_bp = [value(OCT_06, "2.62"), value(OCT_07, "2.87")]
    at_50_bp = [value(OCT_06, "2.62"), value(OCT_07, "3.12")]

    assert check_jumps(at_25_bp, OCT_06, ECB_AAA_SPOT) == []

    findings = check_jumps(at_50_bp, OCT_06, ECB_AAA_SPOT)
    assert [finding.severity for finding in findings] == [Severity.INFO]


def test_range_bounds_are_not_flagged() -> None:
    on_bounds = [value(OCT_06, "-2.00"), value(OCT_07, "8.00")]
    outside = [value(OCT_06, "-2.01"), value(OCT_07, "8.01")]

    assert check_range(on_bounds, ECB_AAA_SPOT) == []

    findings = check_range(outside, ECB_AAA_SPOT)
    assert [finding.severity for finding in findings] == [Severity.WARN, Severity.WARN]
    assert [finding.evidence for finding in findings] == [
        "-2.01 % on 2026-10-06",
        "8.01 % on 2026-10-07",
    ]


def test_a_jump_skips_a_gap_to_the_previous_value() -> None:
    friday = date(2026, 10, 2)
    monday = date(2026, 10, 5)
    series = [value(friday, "2.62"), value(monday, "2.92")]

    findings = check_jumps(series, friday, ECB_AAA_SPOT)

    assert len(findings) == 1
    assert findings[0].evidence == "2.92 % on 2026-10-05 after 2.62 % on 2026-10-02 (+30.0 bp)"


def test_the_first_value_has_no_jump() -> None:
    assert check_jumps([value(OCT_08, "26.40")], OCT_08, ECB_AAA_SPOT) == []


def test_lead_in_values_are_not_assessed_but_serve_as_predecessor() -> None:
    series = [value(OCT_06, "2.62"), value(OCT_07, "2.92"), value(OCT_08, "2.93")]

    findings = check_jumps(series, OCT_07, ECB_AAA_SPOT)

    assert [finding.valid_date for finding in findings] == [OCT_07]


def test_no_jump_is_checked_after_more_than_31_days() -> None:
    sept_01 = date(2026, 9, 1)
    at_31_days = [value(sept_01, "2.62"), value(date(2026, 10, 2), "26.40")]
    after_31_days = [value(sept_01, "2.62"), value(date(2026, 10, 3), "26.40")]

    assert len(check_jumps(at_31_days, sept_01, ECB_AAA_SPOT)) == 1
    assert check_jumps(after_31_days, sept_01, ECB_AAA_SPOT) == []


def test_each_finding_carries_its_rule_explanation() -> None:
    findings: list[Finding] = [
        *check_range([value(OCT_08, "26.40")], ECB_AAA_SPOT),
        *check_jumps([value(OCT_06, "2.62"), value(OCT_07, "2.92")], OCT_06, ECB_AAA_SPOT),
        *check_jumps([value(OCT_06, "2.62"), value(OCT_07, "3.12")], OCT_06, ECB_AAA_SPOT),
    ]

    expected = {
        (Rule.RANGE, Severity.WARN): RANGE_WARN,
        (Rule.JUMP, Severity.INFO): JUMP_INFO,
        (Rule.JUMP, Severity.WARN): JUMP_WARN,
    }
    assert len(findings) == 3
    for finding in findings:
        assert finding.explanation == expected[(finding.rule, finding.severity)]
        assert finding.evidence


def test_a_downward_move_is_flagged_like_an_upward_one() -> None:
    info = check_jumps([value(OCT_06, "2.92"), value(OCT_07, "2.62")], OCT_06, ECB_AAA_SPOT)
    warn = check_jumps([value(OCT_06, "3.12"), value(OCT_07, "2.52")], OCT_06, ECB_AAA_SPOT)

    assert len(info) == 1
    assert info[0].severity is Severity.INFO
    assert info[0].evidence == "2.62 % on 2026-10-07 after 2.92 % on 2026-10-06 (-30.0 bp)"
    assert len(warn) == 1
    assert warn[0].severity is Severity.WARN


def test_exactly_minus_25_bp_is_not_flagged() -> None:
    assert check_jumps([value(OCT_06, "2.87"), value(OCT_07, "2.62")], OCT_06, ECB_AAA_SPOT) == []
