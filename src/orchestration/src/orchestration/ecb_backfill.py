"""Steps of the manual ECB backfill DAG: how a date range is split and which job command loads it.

A range is loaded one calendar year at a time, so each job run makes one history request
per year and the ECB is asked for a bounded window. The job is ``ingestion-load-ecb
history`` (see ``docs/project/00-data-ingestion/03-ecb-load.md``). Running and failure
reporting are shared with the daily DAG in ``ecb_daily_load``.
"""

from datetime import date

from orchestration.ecb_daily_load import JOB_COMMAND


def backfill_years(start: date, end: date) -> list[tuple[date, date]]:
    """Split ``start`` to ``end`` (both inclusive) into one chunk per calendar year.

    The first and last chunk are clipped to ``start`` and ``end``.
    """
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    return [
        (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)))
        for year in range(start.year, end.year + 1)
    ]


def history_command(start: date, end: date, run_id: str) -> list[str]:
    return [
        JOB_COMMAND,
        "history",
        "--start",
        start.isoformat(),
        "--end",
        end.isoformat(),
        "--run-id",
        run_id,
    ]
