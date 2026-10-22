from datetime import date
from decimal import Decimal

import pytest

from processing.domain.calendar import TARGET
from processing.domain.explanations import ECB_AAA_SPOT_EXPLANATIONS
from processing.domain.quality import Severity
from processing.domain.rule_config import (
    ECB_AAA_SPOT,
    ECB_AAA_SPOT_RULES,
    RULES_BY_CURVE,
    CurveRules,
    MaturityPeriod,
)


def test_the_simulated_curve_uses_the_real_curve_rules() -> None:
    assert RULES_BY_CURVE["ecb-aaa-spot-sim"] is RULES_BY_CURVE["ecb-aaa-spot"]


def test_the_ecb_thresholds_match_the_methodology_note() -> None:
    assert ECB_AAA_SPOT.range_min == Decimal("-2.00")
    assert ECB_AAA_SPOT.range_max == Decimal("8.00")
    assert ECB_AAA_SPOT.jump_info_bp == Decimal("25")
    assert ECB_AAA_SPOT.jump_warn_bp == Decimal("50")
    assert ECB_AAA_SPOT_RULES.thresholds is ECB_AAA_SPOT


def test_the_ecb_curves_use_the_ecb_explanations() -> None:
    assert ECB_AAA_SPOT_RULES.explanations is ECB_AAA_SPOT_EXPLANATIONS


def test_the_ecb_curves_use_the_target_calendar() -> None:
    assert ECB_AAA_SPOT_RULES.calendar is TARGET


def test_the_ecb_curves_expect_the_full_grid_v1_on_every_day() -> None:
    grid = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
    for day in (date(1999, 1, 4), date(2004, 9, 6), date(2026, 10, 21)):
        assert ECB_AAA_SPOT_RULES.maturities_on(day) == grid


def test_expected_maturities_follow_the_period_of_the_day() -> None:
    rules = CurveRules(
        ECB_AAA_SPOT,
        TARGET,
        (
            MaturityPeriod(date(1990, 1, 2), ("10Y",)),
            MaturityPeriod(date(1993, 10, 1), ("10Y", "20Y")),
        ),
        ECB_AAA_SPOT_EXPLANATIONS,
    )

    assert rules.maturities_on(date(1990, 1, 1)) == ()
    assert rules.maturities_on(date(1990, 1, 2)) == ("10Y",)
    assert rules.maturities_on(date(1993, 9, 30)) == ("10Y",)
    assert rules.maturities_on(date(1993, 10, 1)) == ("10Y", "20Y")


@pytest.mark.parametrize(
    "periods",
    [
        (),
        (MaturityPeriod(date(1990, 1, 2), ("10Y",)), MaturityPeriod(date(1990, 1, 2), ("20Y",))),
        (MaturityPeriod(date(1993, 10, 1), ("10Y",)), MaturityPeriod(date(1990, 1, 2), ("20Y",))),
    ],
)
def test_periods_must_start_in_ascending_order(periods: tuple[MaturityPeriod, ...]) -> None:
    with pytest.raises(ValueError, match="strictly ascending"):
        CurveRules(ECB_AAA_SPOT, TARGET, periods, ECB_AAA_SPOT_EXPLANATIONS)


def test_severity_is_warn_or_info_only() -> None:
    assert {severity.value for severity in Severity} == {"warn", "info"}
