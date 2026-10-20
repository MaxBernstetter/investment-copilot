"""Command line of the quality check job: a curve and date range in, a JSON summary out.

    processing-check-quality CURVE_ID --from D --to D [--run-id ID]

The run id defaults to ``check-quality-<curve>-<from>-<to>``. A usage error or an unknown
curve exits with status 2; persistence or Oracle failures exit with status 1.
"""

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from processing.application.check_quality import CheckSummary


@dataclass(frozen=True, slots=True)
class CheckCommand:
    curve_id: str
    valid_from: date
    valid_to: date
    run_id: str


def parse_command(argv: Sequence[str] | None) -> CheckCommand:
    """Parse the arguments; exits with status 2 on a usage error (argparse)."""
    parser = argparse.ArgumentParser(
        prog="processing-check-quality",
        description="Check the quality of one published curve over a valid-date range.",
    )
    parser.add_argument("curve_id")
    parser.add_argument("--from", dest="valid_from", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="valid_to", type=date.fromisoformat, required=True)
    parser.add_argument("--run-id", help="defaults to check-quality-<curve>-<from>-<to>")
    arguments = parser.parse_args(argv)
    if arguments.valid_from > arguments.valid_to:
        parser.error(
            f"--from {arguments.valid_from} is after --to {arguments.valid_to}",
        )
    run_id = (
        arguments.run_id
        or f"check-quality-{arguments.curve_id}-{arguments.valid_from}-{arguments.valid_to}"
    )
    return CheckCommand(arguments.curve_id, arguments.valid_from, arguments.valid_to, run_id)


def summary(result: CheckSummary, trace: Mapping[str, str]) -> str:
    """One JSON line describing the finished check, with the trace ids of its root span."""
    return json.dumps(
        {
            "event": "quality_checked",
            "curve_id": result.curve_id,
            "run_id": result.run_id,
            "checked_as_of": (
                result.checked_as_of.isoformat() if result.checked_as_of is not None else None
            ),
            "chunks": result.chunks,
            "days": result.days,
            "values": result.values,
            "warn_count": result.warn_count,
            "info_count": result.info_count,
            **trace,
        }
    )


def failure(run_id: str | None, error: Exception, trace: Mapping[str, str]) -> str:
    """One JSON line describing a failed check, with the trace ids of its root span."""
    return json.dumps(
        {
            "event": "quality_check_failed",
            "run_id": run_id,
            "error": type(error).__name__,
            "message": str(error),
            **trace,
        }
    )
