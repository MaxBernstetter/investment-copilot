"""Scenario events: a simulated curve written in steps, with no I/O.

A scenario is a named sequence of events. Each event writes some values of one
simulated curve (never a real one), so a scenario can show how the core handles gaps,
bad values, late values and corrections.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

SCENARIO_SOURCE_ID = "scenario"
"""Source id of every scenario value, so simulated values are told apart from published ones."""


class EventKind(StrEnum):
    PUBLISH = "publish"
    GAP = "gap"
    BAD_VALUE = "bad value"
    LATE_VALUE = "late value"
    CORRECTION = "correction"


class ScenarioChangeReason(StrEnum):
    """The change reason a scenario event is recorded with."""

    INITIAL = "initial"
    CORRECTION = "correction"


class UnknownEventError(LookupError):
    """A scenario has no event of the given name."""


@dataclass(frozen=True, slots=True)
class ScenarioValue:
    """One value of the simulated curve, in percent."""

    valid_date: date
    maturity: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class ScenarioEvent:
    """One step of a scenario: the values it writes and what they show."""

    name: str
    kind: EventKind
    description: str
    values: tuple[ScenarioValue, ...]

    @property
    def change_reason(self) -> ScenarioChangeReason:
        if self.kind is EventKind.CORRECTION:
            return ScenarioChangeReason.CORRECTION
        return ScenarioChangeReason.INITIAL


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    curve_id: str
    """The simulated curve every event writes to."""
    events: tuple[ScenarioEvent, ...]

    def event(self, name: str) -> ScenarioEvent:
        for event in self.events:
            if event.name == name:
                return event
        raise UnknownEventError(f"Scenario {self.name} has no event {name}")
