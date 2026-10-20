"""Thresholds of the plausibility rules, configured per curve."""

from dataclasses import dataclass
from decimal import Decimal

RULE_SET_VERSION = "1"


@dataclass(frozen=True, slots=True)
class PlausibilityThresholds:
    """Range bounds in percent and jump thresholds in basis points. Comparisons are strict."""

    range_min: Decimal
    range_max: Decimal
    jump_info_bp: Decimal
    jump_warn_bp: Decimal


ECB_AAA_SPOT = PlausibilityThresholds(
    range_min=Decimal("-2.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    range_max=Decimal("8.00"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_info_bp=Decimal("25"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
    jump_warn_bp=Decimal("50"),  # docs/project/02-data-processing/01-plausibility-thresholds.md
)

THRESHOLDS_BY_CURVE: dict[str, PlausibilityThresholds] = {
    "ecb-aaa-spot": ECB_AAA_SPOT,
    "ecb-aaa-spot-sim": ECB_AAA_SPOT,
}
