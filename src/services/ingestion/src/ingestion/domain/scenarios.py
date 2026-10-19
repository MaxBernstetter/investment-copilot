"""The predefined scenarios: a simulated curve with corrected yields. No I/O."""

from datetime import date
from decimal import Decimal

from ingestion.domain.scenario import EventKind, Scenario, ScenarioEvent, ScenarioValue

SIMULATED_CURVE_ID = "ecb-aaa-spot-sim"
"""The simulated curve; scenarios never write to a real curve."""

BASE_CURVE: dict[str, Decimal] = {
    "3M": Decimal("1.95"),
    "6M": Decimal("1.93"),
    "1Y": Decimal("1.90"),
    "2Y": Decimal("1.95"),
    "3Y": Decimal("2.02"),
    "5Y": Decimal("2.18"),
    "7Y": Decimal("2.36"),
    "10Y": Decimal("2.61"),
    "15Y": Decimal("2.86"),
    "20Y": Decimal("2.98"),
    "30Y": Decimal("3.01"),
}


def _curve(
    valid_date: date,
    shift: str,
    *,
    without: tuple[str, ...] = (),
    overrides: dict[str, str] | None = None,
) -> tuple[ScenarioValue, ...]:
    """The base curve shifted by ``shift``, in grid order; ``overrides`` are absolute values."""
    absolute = {maturity: Decimal(value) for maturity, value in (overrides or {}).items()}
    return tuple(
        ScenarioValue(
            valid_date,
            maturity,
            absolute.get(maturity, base + Decimal(shift)),
        )
        for maturity, base in BASE_CURVE.items()
        if maturity not in without
    )


CORRECTED_YIELD = Scenario(
    "corrected-yield",
    SIMULATED_CURVE_ID,
    (
        ScenarioEvent(
            "publish",
            EventKind.PUBLISH,
            "The simulated curve is published for two days.",
            _curve(date(2026, 10, 5), "0.00") + _curve(date(2026, 10, 6), "0.01"),
        ),
        ScenarioEvent(
            "gap",
            EventKind.GAP,
            "The 10Y and 30Y yields of 2026-10-07 are missing.",
            _curve(date(2026, 10, 7), "0.02", without=("10Y", "30Y")),
        ),
        ScenarioEvent(
            "bad-value",
            EventKind.BAD_VALUE,
            "The 10Y yield of 2026-10-08 is published with an implausible value of 26.40.",
            _curve(date(2026, 10, 8), "0.03", overrides={"10Y": "26.40"}),
        ),
        ScenarioEvent(
            "late-value",
            EventKind.LATE_VALUE,
            "The missing 10Y and 30Y yields of 2026-10-07 arrive late.",
            (
                ScenarioValue(date(2026, 10, 7), "10Y", Decimal("2.63")),
                ScenarioValue(date(2026, 10, 7), "30Y", Decimal("3.03")),
            ),
        ),
        ScenarioEvent(
            "correction",
            EventKind.CORRECTION,
            "The source corrects the 10Y yield of 2026-10-08 to 2.64.",
            (ScenarioValue(date(2026, 10, 8), "10Y", Decimal("2.64")),),
        ),
    ),
)

SCENARIOS: dict[str, Scenario] = {CORRECTED_YIELD.name: CORRECTED_YIELD}
