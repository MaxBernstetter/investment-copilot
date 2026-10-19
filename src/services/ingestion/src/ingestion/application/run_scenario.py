"""Use case: write the events of a scenario to its simulated curve, one at a time."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ingestion.application.load_published_curve import RecordedBatch
from ingestion.domain.scenario import EventKind, Scenario, ScenarioEvent

EVENT_PAUSE_SECONDS = 2.0
"""Pause between two events, so a seconds-precision as-of picker can land between two events."""


class ScenarioStore(Protocol):
    """Port: records the values of one scenario event as versions of a curve."""

    async def record_event(
        self, curve_id: str, event: ScenarioEvent, run_id: str
    ) -> RecordedBatch: ...


@dataclass(frozen=True, slots=True)
class EventResult:
    name: str
    kind: EventKind
    run_id: str
    batch: RecordedBatch


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: str
    curve_id: str
    events: tuple[EventResult, ...]


class RunScenario:
    """Write the events of a scenario in order, pausing between them.

    All event names are resolved before the first write, so an unknown name writes
    nothing.
    """

    def __init__(
        self, store: ScenarioStore, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    ) -> None:
        self._store = store
        self._sleep = sleep

    async def __call__(
        self, scenario: Scenario, event_names: Sequence[str] | None = None
    ) -> ScenarioResult:
        if event_names is None:
            events = list(scenario.events)
        else:
            events = [scenario.event(name) for name in event_names]
        results: list[EventResult] = []
        for index, event in enumerate(events):
            if index:
                await self._sleep(EVENT_PAUSE_SECONDS)
            run_id = f"scenario-{scenario.name}-{event.name}"
            batch = await self._store.record_event(scenario.curve_id, event, run_id)
            results.append(EventResult(event.name, event.kind, run_id, batch))
        return ScenarioResult(scenario.name, scenario.curve_id, tuple(results))
