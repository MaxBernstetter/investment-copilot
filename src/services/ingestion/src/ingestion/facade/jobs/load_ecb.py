"""Command line of the ECB load job: arguments in, a JSON run summary out.

    ingestion-load-ecb daily --valid-date 2026-10-15 [--run-id ID]
    ingestion-load-ecb history --start 2004-09-06 --end 2026-10-16 [--run-id ID]
    ingestion-load-ecb replay --fetched-from 2026-10-01 --fetched-to 2026-10-18 [--run-id ID]

``daily`` loads the valid date and the lookback window before it
(``INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS``). ``history`` loads a range with
one request per calendar year. ``replay`` parses the deliveries stored in ``ING`` that
were fetched on those days (UTC) again and records their values, without calling the
ECB. The run id defaults to a deterministic value derived
from the command and its dates, so a rerun of the same load reuses it.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ingestion.application.load_published_curve import LoadResult
from ingestion.application.replay_deliveries import ReplayResult
from ingestion.domain.windows import DateWindow, lookback_window, yearly_windows


@dataclass(frozen=True, slots=True)
class LoadCommand:
    windows: tuple[DateWindow, ...]
    run_id: str


@dataclass(frozen=True, slots=True)
class ReplayCommand:
    fetched_from: date
    fetched_to: date
    run_id: str


def parse_command(
    argv: Sequence[str] | None, *, lookback_business_days: int
) -> LoadCommand | ReplayCommand:
    """Parse the arguments; exits with status 2 on a usage error (argparse)."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "daily":
        valid_date: date = arguments.valid_date
        window = lookback_window(valid_date, lookback_business_days)
        return LoadCommand((window,), arguments.run_id or f"ecb-daily-{valid_date}")
    if arguments.command == "replay":
        fetched_from: date = arguments.fetched_from
        fetched_to: date = arguments.fetched_to
        if fetched_from > fetched_to:
            parser.error(f"--fetched-from {fetched_from} is after --fetched-to {fetched_to}")
        run_id = arguments.run_id or f"ecb-replay-{fetched_from}-{fetched_to}"
        return ReplayCommand(fetched_from, fetched_to, run_id)
    start: date = arguments.start
    end: date = arguments.end
    if start > end:
        parser.error(f"--start {start} is after --end {end}")
    windows = yearly_windows(DateWindow(start, end))
    return LoadCommand(tuple(windows), arguments.run_id or f"ecb-history-{start}-{end}")


def summary(result: LoadResult) -> str:
    """One JSON line describing the finished run."""
    return json.dumps(
        {
            "event": "load_finished",
            "source": "ecb",
            "run_id": result.run_id,
            "delivered_count": result.delivered_count,
            "recorded_count": result.recorded_count,
            "unchanged_count": result.unchanged_count,
            "windows": [
                {
                    "start": window.window.start.isoformat(),
                    "end": window.window.end.isoformat(),
                    "delivery_id": window.delivery_id,
                    "delivered_count": window.delivered_count,
                    "recorded_count": sum(batch.recorded_count for batch in window.batches),
                    "unchanged_count": sum(batch.unchanged_count for batch in window.batches),
                    "known_from": [batch.known_from.isoformat() for batch in window.batches],
                    "last_modified": (
                        window.last_modified.isoformat() if window.last_modified else None
                    ),
                }
                for window in result.windows
            ],
        }
    )


def replay_summary(result: ReplayResult) -> str:
    """One JSON line describing the finished replay."""
    return json.dumps(
        {
            "event": "replay_finished",
            "source": "ecb",
            "run_id": result.run_id,
            "delivered_count": result.delivered_count,
            "recorded_count": result.recorded_count,
            "unchanged_count": result.unchanged_count,
            "deliveries": [
                {
                    "delivery_id": delivery.delivery_id,
                    "delivered_count": delivery.delivered_count,
                    "recorded_count": sum(b.recorded_count for b in delivery.batches),
                    "unchanged_count": sum(b.unchanged_count for b in delivery.batches),
                }
                for delivery in result.deliveries
            ],
        }
    )


def failure(run_id: str | None, error: Exception) -> str:
    """One JSON line describing a failed run."""
    return json.dumps(
        {
            "event": "load_failed",
            "source": "ecb",
            "run_id": run_id,
            "error": type(error).__name__,
            "message": str(error),
        }
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingestion-load-ecb",
        description="Load the ECB euro area AAA spot curve into the bitemporal core.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    daily = commands.add_parser("daily", help="one valid date plus its lookback window")
    daily.add_argument("--valid-date", type=date.fromisoformat, required=True)
    history = commands.add_parser("history", help="a date range, one request per year")
    history.add_argument("--start", type=date.fromisoformat, required=True)
    history.add_argument("--end", type=date.fromisoformat, required=True)
    replay = commands.add_parser(
        "replay", help="parse stored deliveries again, without calling the source"
    )
    replay.add_argument("--fetched-from", type=date.fromisoformat, required=True)
    replay.add_argument("--fetched-to", type=date.fromisoformat, required=True)
    for command in (daily, history, replay):
        command.add_argument("--run-id", help="defaults to a value derived from the dates")
    return parser
