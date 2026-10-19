from datetime import date
from decimal import Decimal

import pytest

from ingestion.domain.scenario import EventKind, ScenarioChangeReason, UnknownEventError
from ingestion.domain.scenarios import CORRECTED_YIELD, SCENARIOS, SIMULATED_CURVE_ID


def test_every_event_writes_the_simulated_curve_only() -> None:
    assert CORRECTED_YIELD.curve_id == SIMULATED_CURVE_ID
    assert {CORRECTED_YIELD.name: CORRECTED_YIELD} == SCENARIOS
    assert SIMULATED_CURVE_ID != "ecb-aaa-spot"


def test_event_names_are_unique() -> None:
    names = [event.name for event in CORRECTED_YIELD.events]

    assert len(names) == len(set(names))


def test_corrected_yield_has_a_gap_a_bad_value_a_late_value_and_a_correction() -> None:
    kinds = [event.kind for event in CORRECTED_YIELD.events]

    assert kinds == [
        EventKind.PUBLISH,
        EventKind.GAP,
        EventKind.BAD_VALUE,
        EventKind.LATE_VALUE,
        EventKind.CORRECTION,
    ]
    gap = CORRECTED_YIELD.event("gap")
    assert {"10Y", "30Y"}.isdisjoint(value.maturity for value in gap.values)
    bad = CORRECTED_YIELD.event("bad-value")
    assert (date(2026, 10, 8), "10Y", Decimal("26.40")) in {
        (value.valid_date, value.maturity, value.value) for value in bad.values
    }
    late = CORRECTED_YIELD.event("late-value")
    assert {(value.maturity, value.value) for value in late.values} == {
        ("10Y", Decimal("2.63")),
        ("30Y", Decimal("3.03")),
    }
    assert all(value.valid_date == date(2026, 10, 7) for value in late.values)
    correction = CORRECTED_YIELD.event("correction")
    assert [(value.valid_date, value.maturity, value.value) for value in correction.values] == [
        (date(2026, 10, 8), "10Y", Decimal("2.64"))
    ]


def test_only_the_correction_is_sent_as_correction() -> None:
    reasons = {event.name: event.change_reason for event in CORRECTED_YIELD.events}

    assert reasons == {
        "publish": ScenarioChangeReason.INITIAL,
        "gap": ScenarioChangeReason.INITIAL,
        "bad-value": ScenarioChangeReason.INITIAL,
        "late-value": ScenarioChangeReason.INITIAL,
        "correction": ScenarioChangeReason.CORRECTION,
    }


def test_unknown_event_is_an_error() -> None:
    with pytest.raises(UnknownEventError, match="Scenario corrected-yield has no event nope"):
        CORRECTED_YIELD.event("nope")
