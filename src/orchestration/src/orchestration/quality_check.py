"""Steps of the quality-check tasks: which curve and range to check and how to run the job.

The job is ``processing-check-quality`` (see the processing service note under
``docs/project/02-data-processing/``). Exit status and subprocess handling are shared with the
load tasks in ``ecb_daily_load``.
"""

from datetime import date, timedelta

JOB_COMMAND = "processing-check-quality"
DAILY_WINDOW = timedelta(days=21)


def daily_check_command(curve_id: str, valid_date: date, run_id: str) -> list[str]:
    """Check the three weeks up to and including ``valid_date`` (the day the daily load wrote)."""
    return range_check_command(curve_id, valid_date - DAILY_WINDOW, valid_date, run_id)


def range_check_command(curve_id: str, start: date, end: date, run_id: str) -> list[str]:
    return [
        JOB_COMMAND,
        curve_id,
        "--from",
        start.isoformat(),
        "--to",
        end.isoformat(),
        "--run-id",
        run_id,
    ]
