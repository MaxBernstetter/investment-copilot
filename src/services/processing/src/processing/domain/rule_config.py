"""Quality rules configured per curve: thresholds, calendar and expected maturities."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from processing.domain.calendar import TARGET, BusinessCalendar

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
    """The quality rules of one curve: thresholds, calendar, expected maturities."""

    thresholds: PlausibilityThresholds
    calendar: BusinessCalendar
    expected_maturities: tuple[MaturityPeriod, ...]

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

ECB_GRID_V1_MATURITIES = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")

ECB_AAA_SPOT_RULES = CurveRules(
    thresholds=ECB_AAA_SPOT,
    calendar=TARGET,
    # date.min: the full grid v1 is expected on every day, as before #262.
    expected_maturities=(MaturityPeriod(start=date.min, maturities=ECB_GRID_V1_MATURITIES),),
)

RULES_BY_CURVE: dict[str, CurveRules] = {
    "ecb-aaa-spot": ECB_AAA_SPOT_RULES,
    "ecb-aaa-spot-sim": ECB_AAA_SPOT_RULES,
}
