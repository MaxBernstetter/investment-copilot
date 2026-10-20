from decimal import Decimal

from processing.domain.quality import Severity
from processing.domain.rule_config import ECB_AAA_SPOT, THRESHOLDS_BY_CURVE


def test_the_simulated_curve_uses_the_real_curve_thresholds() -> None:
    assert THRESHOLDS_BY_CURVE["ecb-aaa-spot-sim"] is THRESHOLDS_BY_CURVE["ecb-aaa-spot"]


def test_the_ecb_thresholds_match_the_methodology_note() -> None:
    assert ECB_AAA_SPOT.range_min == Decimal("-2.00")
    assert ECB_AAA_SPOT.range_max == Decimal("8.00")
    assert ECB_AAA_SPOT.jump_info_bp == Decimal("25")
    assert ECB_AAA_SPOT.jump_warn_bp == Decimal("50")


def test_severity_is_warn_or_info_only() -> None:
    assert {severity.value for severity in Severity} == {"warn", "info"}
