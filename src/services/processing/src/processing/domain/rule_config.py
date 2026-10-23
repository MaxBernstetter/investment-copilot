"""Quality rules configured per curve: thresholds, calendar and expected maturities."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from processing.domain.calendar import TARGET, US_BOND_MARKET, BusinessCalendar
from processing.domain.explanations import (
    ECB_AAA_SPOT_EXPLANATIONS,
    ECB_ALL_SPOT_EXPLANATIONS,
    UST_PAR_EXPLANATIONS,
    Explanations,
)

RULE_SET_VERSION = "1"


@dataclass(frozen=True, slots=True)
class PlausibilityThresholds:
    """Range bounds in percent and jump thresholds in basis points. Comparisons are strict."""

    range_min: Decimal
    range_max: Decimal
    jump_info_bp: Decimal
    jump_warn_bp: Decimal


@dataclass(frozen=True, slots=True)
class MaturityPeriod:
    """The maturities expected on every business day from ``start`` until the next period starts."""

    start: date
    maturities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurveRules:
    """The quality rules of one curve: thresholds, calendar, expected maturities, texts."""

    thresholds: PlausibilityThresholds
    calendar: BusinessCalendar
    expected_maturities: tuple[MaturityPeriod, ...]
    explanations: Explanations

    def __post_init__(self) -> None:
        starts = [period.start for period in self.expected_maturities]
        if not starts or starts != sorted(set(starts)):
            raise ValueError(
                "expected maturity periods must exist and start in strictly ascending order"
            )

    def maturities_on(self, day: date) -> tuple[str, ...]:
        """The maturities expected on ``day``; none before the first period."""
        expected: tuple[str, ...] = ()
        for period in self.expected_maturities:
            if period.start > day:
                break
            expected = period.maturities
        return expected


ECB_AAA_SPOT = PlausibilityThresholds(
    range_min=Decimal("-2.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    range_max=Decimal("8.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_info_bp=Decimal("25"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_warn_bp=Decimal("50"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
)
ECB_ALL_SPOT = PlausibilityThresholds(
    range_min=Decimal("-2.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    range_max=Decimal("8.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_info_bp=Decimal("25"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_warn_bp=Decimal("50"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
)

ECB_GRID_V1_MATURITIES = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")

ECB_AAA_SPOT_RULES = CurveRules(
    thresholds=ECB_AAA_SPOT,
    calendar=TARGET,
    # date.min: the full grid v1 is expected on every day, as before #262.
    expected_maturities=(MaturityPeriod(start=date.min, maturities=ECB_GRID_V1_MATURITIES),),
    explanations=ECB_AAA_SPOT_EXPLANATIONS,
)

ECB_ALL_SPOT_RULES = CurveRules(
    thresholds=ECB_ALL_SPOT,
    calendar=TARGET,
    # Published on grid v1 since 2004-09-06, like the AAA curve.
    expected_maturities=(MaturityPeriod(start=date.min, maturities=ECB_GRID_V1_MATURITIES),),
    explanations=ECB_ALL_SPOT_EXPLANATIONS,
)

# PROVISIONAL: derived by hand from the Treasury history 1990 to 2026 (no value below 0.00 % or
# above 9.18 %; see docs/project/02-data-processing/01-plausibility-thresholds.md, "US Treasury").
# The --source ust derivation in the script is a follow-up (MR3b), so these stay provisional.
UST_PAR = PlausibilityThresholds(
    range_min=Decimal("-0.50"),
    range_max=Decimal("10.00"),
    jump_info_bp=Decimal("25"),
    jump_warn_bp=Decimal("50"),
)

# Grid 2 tenors in ascending order. The Treasury columns appear and disappear over time (#266):
# 1M from 2001-07-31, 20Y from 1993-10-01, 30Y not from 2002-02-19 to 2006-02-08, 2M from
# 2018-10-16, 4M from 2022-10-19, 1.5M from 2025-02-18.
UST_PAR_RULES = CurveRules(
    thresholds=UST_PAR,
    calendar=US_BOND_MARKET,
    expected_maturities=(
        MaturityPeriod(
            start=date(1990, 1, 2),
            maturities=("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"),
        ),
        MaturityPeriod(
            start=date(1993, 10, 1),
            maturities=("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"),
        ),
        MaturityPeriod(
            start=date(2001, 7, 31),
            maturities=("1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"),
        ),
        MaturityPeriod(
            start=date(2002, 2, 19),
            maturities=("1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y"),
        ),
        MaturityPeriod(
            start=date(2006, 2, 9),
            maturities=("1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"),
        ),
        MaturityPeriod(
            start=date(2018, 10, 16),
            maturities=("1M", "2M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"),
        ),
        MaturityPeriod(
            start=date(2022, 10, 19),
            maturities=(
                "1M",
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
            ),
        ),
        MaturityPeriod(
            start=date(2025, 2, 18),
            maturities=(
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
            ),
        ),
    ),
    explanations=UST_PAR_EXPLANATIONS,
)

RULES_BY_CURVE: dict[str, CurveRules] = {
    "ecb-aaa-spot": ECB_AAA_SPOT_RULES,
    "ecb-all-spot": ECB_ALL_SPOT_RULES,
    "ecb-aaa-spot-sim": ECB_AAA_SPOT_RULES,
    "ust-par": UST_PAR_RULES,
}
