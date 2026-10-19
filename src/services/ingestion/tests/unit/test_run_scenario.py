"""RunScenario against a fake store and a recording sleep. No I/O."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from ingestion.application.load_published_curve import RecordedBatch
from ingestion.application.run_scenario import EVENT_PAUSE_SECONDS, RunScenario
from ingestion.domain.scenario import EventKind, ScenarioEvent, UnknownEventError
from ingestion.domain.scenarios import CORRECTED_YIELD, SIMULATED_CURVE_ID

pytestmark = pytest.mark.anyio


@dataclass
class FakeStore:
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    async def record_event(self, curve_id: str, event: ScenarioEvent, run_id: str) -> RecordedBatch:
        self.calls.append((curve_id, event.name, run_id))
        return RecordedBatch(len(event.values), 0, _KNOWN_FROM)


@dataclass
class RecordingSleep:
    waits: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


_KNOWN_FROM = datetime(2026, 10, 18, 9, 30, tzinfo=UTC)


async def test_runs_all_events_in_order_with_a_pause_between() -> None:
    store = FakeStore()
    sleep = RecordingSleep()

    result = await RunScenario(store, sleep)(CORRECTED_YIELD)

    assert [name for _, name, _ in store.calls] == [
        "publish",
        "gap",
        "bad-value",
        "late-value",
        "correction",
    ]
    assert sleep.waits == [EVENT_PAUSE_SECONDS] * 4
    assert [event.kind for event in result.events] == [
        EventKind.PUBLISH,
        EventKind.GAP,
        EventKind.BAD_VALUE,
        EventKind.LATE_VALUE,
        EventKind.CORRECTION,
    ]
    assert result.scenario == "corrected-yield"
    assert result.curve_id == SIMULATED_CURVE_ID


async def test_runs_only_the_named_event() -> None:
    store = FakeStore()
    sleep = RecordingSleep()

    result = await RunScenario(store, sleep)(CORRECTED_YIELD, ["correction", "gap"])

    assert [name for _, name, _ in store.calls] == ["correction", "gap"]
    assert sleep.waits == [EVENT_PAUSE_SECONDS]
    assert [event.name for event in result.events] == ["correction", "gap"]


async def test_unknown_event_writes_nothing() -> None:
    store = FakeStore()
    sleep = RecordingSleep()

    with pytest.raises(UnknownEventError):
        await RunScenario(store, sleep)(CORRECTED_YIELD, ["gap", "nope"])

    assert store.calls == []
    assert sleep.waits == []


async def test_run_id_names_scenario_and_event() -> None:
    store = FakeStore()

    result = await RunScenario(store, RecordingSleep())(CORRECTED_YIELD, ["bad-value"])

    assert store.calls == [(SIMULATED_CURVE_ID, "bad-value", "scenario-corrected-yield-bad-value")]
    assert result.events[0].run_id == "scenario-corrected-yield-bad-value"
