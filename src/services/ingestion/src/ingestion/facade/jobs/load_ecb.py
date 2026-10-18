"""Command line of the ECB load job: arguments in, a JSON run summary out.

    ingestion-load-ecb daily --valid-date 2026-10-15 [--run-id ID]
    ingestion-load-ecb history --start 2004-09-06 --end 2026-10-16 [--run-id ID]
    ingestion-load-ecb drain

``daily`` loads the valid date and the lookback window before it
(``INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS``). ``history`` loads a range with
one request per calendar year. The run id defaults to a deterministic value derived
from the command and its dates, so a rerun of the same load reuses it. Every command
first records what the spool holds; ``drain`` does only that and fetches nothing.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ingestion.application.load_published_curve import LoadResult, WindowResult
from ingestion.domain.windows import DateWindow, lookback_window, yearly_windows


@dataclass(frozen=True, slots=True)
class LoadCommand:
    windows: tuple[DateWindow, ...]
    run_id: str


def parse_command(argv: Sequence[str] | None, *, lookback_business_days: int) -> LoadCommand:
    """Parse the arguments; exits with status 2 on a usage error (argparse)."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "drain":
        return LoadCommand((), "ecb-drain")
    if arguments.command == "daily":
        valid_date: date = arguments.valid_date
        window = lookback_window(valid_date, lookback_business_days)
        return LoadCommand((window,), arguments.run_id or f"ecb-daily-{valid_date}")
    start: date = arguments.start
    end: date = arguments.end
    if start > end:
        parser.error(f"--start {start} is after --end {end}")
    windows = yearly_windows(DateWindow(start, end))
    return LoadCommand(tuple(windows), arguments.run_id or f"ecb-history-{start}-{end}")


def summary(result: LoadResult) -> str:
    """One JSON line describing the finished run: ``load_deferred`` while data waits
    in the spool, ``load_finished`` otherwise."""
    return json.dumps(
        {
            "event": "load_deferred" if result.is_deferred else "load_finished",
            "source": "ecb",
            "run_id": result.run_id,
            "delivered_count": result.delivered_count,
            "recorded_count": result.recorded_count,
            "unchanged_count": result.unchanged_count,
            "windows": [_window(window) for window in result.windows],
            "spooled_windows": [
                {"start": window.start.isoformat(), "end": window.end.isoformat()}
                for window in result.spooled
            ],
            "drained": {
                "windows": [_window(window) for window in result.drain.recorded],
                "rejected": [
                    {"key": item.key, "reason": item.reason} for item in result.drain.rejected
                ],
                "is_blocked": result.drain.is_blocked,
            },
        }
    )


def _window(result: WindowResult) -> dict[str, object]:
    return {
        "start": result.window.start.isoformat(),
        "end": result.window.end.isoformat(),
        "delivered_count": result.delivered_count,
        "recorded_count": result.recorded_count,
        "unchanged_count": result.unchanged_count,
        "known_from": [batch.known_from.isoformat() for batch in result.batches],
        "last_modified": result.last_modified.isoformat() if result.last_modified else None,
    }


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
    commands.add_parser("drain", help="only record what the spool holds; fetch nothing")
    for command in (daily, history):
        command.add_argument("--run-id", help="defaults to a value derived from the dates")
    return parser
