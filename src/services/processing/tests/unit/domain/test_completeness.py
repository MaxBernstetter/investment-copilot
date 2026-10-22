from datetime import date
from decimal import Decimal

from processing.domain.calendar import TARGET
from processing.domain.completeness import check_completeness
from processing.domain.explanations import ECB_AAA_SPOT_EXPLANATIONS
from processing.domain.quality import Rule, Severity, Value
from processing.domain.rule_config import ECB_AAA_SPOT_RULES, CurveRules, MaturityPeriod

ECB_GRID = (
    "3M",
    "6M",
    "1Y",
    "2Y",
    "3Y",
    "5Y",
    "7Y",
    "10Y",
    "15Y",
    "20Y",
    "30Y",
)

OCT_06 = date(2026, 10, 6)
OCT_07 = date(2026, 10, 7)
OCT_08 = date(2026, 10, 8)
GOOD_FRIDAY = date(2026, 4, 3)
SATURDAY = date(2026, 10, 17)


def value(valid_date: date, maturity: str, number: str = "2.61", version_id: int = 1) -> Value:
    return Value(
        version_id=version_id,
        maturity=maturity,
        valid_date=valid_date,
        value=Decimal(number),
    )


def full_day(valid_date: date) -> list[Value]:
    return [value(valid_date, maturity) for maturity in ECB_GRID]


def test_a_business_day_without_any_value_is_a_missing_date_warn() -> None:
    findings = check_completeness([], [OCT_07], ECB_AAA_SPOT_RULES)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule is Rule.MISSING_DATE
    assert finding.severity is Severity.WARN
    assert finding.valid_date == OCT_07
    assert finding.maturity is None
    assert finding.evidence == f"No value for any maturity on {OCT_07}"


def test_weekends_and_target_holidays_are_never_missing() -> None:
    business_days = TARGET.business_days(GOOD_FRIDAY, SATURDAY)

    assert GOOD_FRIDAY not in business_days
    assert SATURDAY not in business_days

    findings = check_completeness([], business_days, ECB_AAA_SPOT_RULES)

    flagged = {finding.valid_date for finding in findings}
    assert GOOD_FRIDAY not in flagged
    assert SATURDAY not in flagged


def test_the_scenario_gap_day_misses_10y_and_30y() -> None:
    gap_day_values = [
        value(OCT_07, maturity) for maturity in ECB_GRID if maturity not in ("10Y", "30Y")
    ]
    values = full_day(OCT_06) + gap_day_values + full_day(OCT_08)

    findings = check_completeness(values, [OCT_06, OCT_07, OCT_08], ECB_AAA_SPOT_RULES)

    assert len(findings) == 2
    assert all(finding.rule is Rule.MISSING_MATURITY for finding in findings)
    assert all(finding.severity is Severity.WARN for finding in findings)
    assert all(finding.valid_date == OCT_07 for finding in findings)
    assert {finding.maturity for finding in findings} == {"10Y", "30Y"}


def test_a_missing_date_reports_no_missing_maturities() -> None:
    values = full_day(OCT_06) + full_day(OCT_08)

    findings = check_completeness(values, [OCT_06, OCT_07, OCT_08], ECB_AAA_SPOT_RULES)

    assert len(findings) == 1
    assert findings[0].rule is Rule.MISSING_DATE
    assert findings[0].valid_date == OCT_07


def test_completeness_findings_explain_their_rule() -> None:
    missing_date = check_completeness([], [OCT_07], ECB_AAA_SPOT_RULES)[0]
    missing_maturity = check_completeness([value(OCT_07, "3M")], [OCT_07], ECB_AAA_SPOT_RULES)[0]

    assert missing_date.explanation == ECB_AAA_SPOT_EXPLANATIONS.missing_date
    assert missing_maturity.explanation == ECB_AAA_SPOT_EXPLANATIONS.missing_maturity


def test_missing_maturities_follow_the_expected_maturities_of_the_day() -> None:
    rules = CurveRules(
        ECB_AAA_SPOT_RULES.thresholds,
        TARGET,
        (MaturityPeriod(OCT_06, ("10Y",)), MaturityPeriod(OCT_08, ("10Y", "30Y"))),
        ECB_AAA_SPOT_EXPLANATIONS,
    )
    values = [value(OCT_07, "10Y"), value(OCT_08, "10Y")]

    findings = check_completeness(values, [OCT_07, OCT_08], rules)

    assert len(findings) == 1
    assert findings[0].rule is Rule.MISSING_MATURITY
    assert findings[0].valid_date == OCT_08
    assert findings[0].maturity == "30Y"
