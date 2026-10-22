from dataclasses import replace
from datetime import date
from decimal import Decimal

from processing.domain.completeness import check_completeness
from processing.domain.explanations import Explanations
from processing.domain.plausibility import check_jumps, check_range
from processing.domain.quality import Value
from processing.domain.rule_config import ECB_AAA_SPOT_RULES

MATURITY = "10Y"
OCT_06 = date(2026, 10, 6)
OCT_07 = date(2026, 10, 7)
OCT_08 = date(2026, 10, 8)


def value(valid_date: date, number: str, maturity: str = MATURITY) -> Value:
    return Value(version_id=1, maturity=maturity, valid_date=valid_date, value=Decimal(number))


def test_findings_take_their_texts_from_the_curve_rules() -> None:
    texts = Explanations("range", "jump info", "jump warn", "missing date", "missing maturity")
    rules = replace(ECB_AAA_SPOT_RULES, explanations=texts)

    assert check_range([value(OCT_08, "26.40")], rules)[0].explanation == "range"
    info = check_jumps([value(OCT_06, "2.62"), value(OCT_07, "2.92")], OCT_06, rules)
    assert info[0].explanation == "jump info"
    warn = check_jumps([value(OCT_06, "2.62"), value(OCT_07, "3.13")], OCT_06, rules)
    assert warn[0].explanation == "jump warn"
    assert check_completeness([], [OCT_07], rules)[0].explanation == "missing date"
    missing = check_completeness([value(OCT_07, "2.61", "3M")], [OCT_07], rules)
    assert missing[0].explanation == "missing maturity"
