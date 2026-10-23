from datetime import date
from decimal import Decimal

import pytest

from processing.domain.calendar import TARGET, US_BOND_MARKET
from processing.domain.explanations import (
    ECB_AAA_SPOT_EXPLANATIONS,
    ECB_ALL_SPOT_EXPLANATIONS,
    UST_PAR_EXPLANATIONS,
)
from processing.domain.quality import Severity
from processing.domain.rule_config import (
    ECB_AAA_SPOT,
    ECB_AAA_SPOT_RULES,
    ECB_ALL_SPOT,
    ECB_ALL_SPOT_RULES,
    RULES_BY_CURVE,
    UST_PAR,
    UST_PAR_RULES,
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


def test_the_all_issuer_thresholds_match_the_methodology_note() -> None:
    assert ECB_ALL_SPOT.range_min == Decimal("-2.00")
    assert ECB_ALL_SPOT.range_max == Decimal("8.00")
    assert ECB_ALL_SPOT.jump_info_bp == Decimal("25")
    assert ECB_ALL_SPOT.jump_warn_bp == Decimal("50")
    assert ECB_ALL_SPOT_RULES.thresholds is ECB_ALL_SPOT


def test_the_all_issuer_curve_has_its_own_rules() -> None:
    assert RULES_BY_CURVE["ecb-all-spot"] is ECB_ALL_SPOT_RULES
    assert ECB_ALL_SPOT_RULES is not ECB_AAA_SPOT_RULES
    assert ECB_ALL_SPOT_RULES.calendar is TARGET
    assert ECB_ALL_SPOT_RULES.explanations is ECB_ALL_SPOT_EXPLANATIONS


def test_the_ecb_curves_use_the_ecb_explanations() -> None:
    assert ECB_AAA_SPOT_RULES.explanations is ECB_AAA_SPOT_EXPLANATIONS


def test_the_ecb_curves_use_the_target_calendar() -> None:
    assert ECB_AAA_SPOT_RULES.calendar is TARGET


@pytest.mark.parametrize("rules", [ECB_AAA_SPOT_RULES, ECB_ALL_SPOT_RULES])
def test_the_ecb_curves_expect_the_full_grid_v1_on_every_day(rules: CurveRules) -> None:
    grid = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
    for day in (date(1999, 1, 4), date(2004, 9, 6), date(2026, 10, 21)):
        assert rules.maturities_on(day) == grid


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


GRID_2_ORDER = (
    "1M",
    "1.5M",
    "2M",
    "3M",
    "4M",
    "6M",
    "1Y",
    "2Y",
    "3Y",
    "5Y",
    "7Y",
    "10Y",
    "20Y",
    "30Y",
)


def test_the_ust_curve_has_its_rules_and_the_us_calendar() -> None:
    assert RULES_BY_CURVE["ust-par"] is UST_PAR_RULES
    assert UST_PAR_RULES.calendar is US_BOND_MARKET
    assert UST_PAR_RULES.explanations is UST_PAR_EXPLANATIONS
    assert UST_PAR.range_min == Decimal("-0.50")
    assert UST_PAR.range_max == Decimal("10.00")
    assert UST_PAR.jump_info_bp == Decimal("25")
    assert UST_PAR.jump_warn_bp == Decimal("50")


def test_the_ust_periods_are_in_grid_2_order_and_start_in_ascending_order() -> None:
    periods = UST_PAR_RULES.expected_maturities
    assert [period.start for period in periods] == sorted({period.start for period in periods})
    for period in periods:
        assert list(period.maturities) == [m for m in GRID_2_ORDER if m in period.maturities]


@pytest.mark.parametrize(
    ("day", "absent", "present"),
    [
        (date(1993, 9, 30), "20Y", "10Y"),  # 20Y from 1993-10-01
        (date(1993, 10, 1), None, "20Y"),
        (date(2001, 7, 30), "1M", "3M"),  # 1M from 2001-07-31
        (date(2001, 7, 31), None, "1M"),
        (date(2002, 2, 18), None, "30Y"),
        (date(2002, 2, 19), "30Y", "20Y"),  # the 30Y gap
        (date(2006, 2, 8), "30Y", "20Y"),
        (date(2006, 2, 9), None, "30Y"),
        (date(2018, 10, 15), "2M", "1M"),  # 2M from 2018-10-16
        (date(2018, 10, 16), None, "2M"),
        (date(2022, 10, 18), "4M", "2M"),  # 4M from 2022-10-19
        (date(2022, 10, 19), None, "4M"),
        (date(2025, 2, 17), "1.5M", "1M"),  # 1.5M from 2025-02-18
        (date(2025, 2, 18), None, "1.5M"),
    ],
)
def test_the_ust_expected_maturities_follow_the_treasury_columns(
    day: date, absent: str | None, present: str
) -> None:
    expected = UST_PAR_RULES.maturities_on(day)

    assert present in expected
    if absent is not None:
        assert absent not in expected


def test_the_ust_curve_expects_nine_tenors_from_1990() -> None:
    assert UST_PAR_RULES.maturities_on(date(1990, 1, 2)) == (
        "3M",
        "6M",
        "1Y",
        "2Y",
        "3Y",
        "5Y",
        "7Y",
        "10Y",
        "30Y",
    )
