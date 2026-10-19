"""Command line of the scenario job: a scenario in, a JSON run summary out.

    ingestion-scenario corrected-yield [--event NAME]...

Without ``--event`` every event of the scenario runs, in order, with a pause between two
events. ``--event`` (repeatable) runs only the named events, in the order given. A
scenario writes to its simulated curve only; it never calls a source.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass

from ingestion.application.run_scenario import ScenarioResult
from ingestion.domain.scenario import Scenario
from ingestion.domain.scenarios import SCENARIOS


@dataclass(frozen=True)
class ScenarioCommand:
    scenario: Scenario
    event_names: tuple[str, ...] | None


def parse_scenario_command(argv: Sequence[str] | None) -> ScenarioCommand:
    """Parse the arguments; exits with status 2 on a usage error (argparse)."""
    parser = argparse.ArgumentParser(
        prog="ingestion-scenario",
        description="Write a scenario's events to its simulated curve, one at a time.",
    )
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument(
        "--event",
        action="append",
        metavar="NAME",
        help="run only this event (repeatable); defaults to all events in order",
    )
    arguments = parser.parse_args(argv)
    scenario = SCENARIOS[arguments.scenario]
    event_names: tuple[str, ...] | None = (
        tuple(arguments.event) if arguments.event is not None else None
    )
    if event_names is not None:
        known = {event.name for event in scenario.events}
        unknown = [name for name in event_names if name not in known]
        if unknown:
            parser.error(
                f"unknown event {', '.join(unknown)} for scenario {scenario.name}; "
                f"known events: {', '.join(sorted(known))}"
            )
    return ScenarioCommand(scenario, event_names)


def scenario_summary(result: ScenarioResult) -> str:
    """One JSON line describing the finished scenario."""
    return json.dumps(
        {
            "event": "scenario_finished",
            "scenario": result.scenario,
            "curve_id": result.curve_id,
            "events": [
                {
                    "name": event.name,
                    "kind": event.kind.value,
                    "run_id": event.run_id,
                    "recorded_count": event.batch.recorded_count,
                    "unchanged_count": event.batch.unchanged_count,
                    "known_from": event.batch.known_from.isoformat(),
                }
                for event in result.events
            ],
        }
    )


def scenario_failure(scenario: str | None, error: Exception) -> str:
    """One JSON line describing a failed scenario run."""
    return json.dumps(
        {
            "event": "scenario_failed",
            "scenario": scenario,
            "error": type(error).__name__,
            "message": str(error),
        }
    )
