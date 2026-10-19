"""Steps of the daily ECB load DAG: which date to load, how to run the job, what to report.

The load itself is the ingestion job ``ingestion-load-ecb`` (see
``docs/project/00-data-ingestion/03-ecb-load.md``). Its exit status decides the retry:
``0`` finished, ``1`` the load failed (retried by Airflow), ``2`` usage or configuration
error (a retry cannot help, so the task fails at once).
"""

import json
import logging
import subprocess
from collections.abc import Sequence
from datetime import date

from airflow.sdk import Context
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

from orchestration.target_calendar import is_target_business_day, previous_target_business_day

JOB_COMMAND = "ingestion-load-ecb"
USAGE_OR_CONFIGURATION_ERROR = 2

log = logging.getLogger(__name__)


class JobFailedError(Exception):
    """The job ended with a status that a retry may fix."""


def valid_date_for(run_day: date) -> date:
    """The valid date a run on ``run_day`` loads: the previous TARGET business day.

    The ECB publishes the curve of a valid date on the next TARGET business day. On a
    TARGET holiday it publishes nothing, so the run is skipped instead of failing.
    """
    if not is_target_business_day(run_day):
        raise AirflowSkipException(f"{run_day} is a TARGET holiday: the ECB publishes nothing")
    return previous_target_business_day(run_day)


def daily_load_command(valid_date: date, run_id: str) -> list[str]:
    return [JOB_COMMAND, "daily", "--valid-date", valid_date.isoformat(), "--run-id", run_id]


def run_job(command: Sequence[str]) -> None:
    """Run the job, pass its JSON output to the task log and map its exit status."""
    finished = subprocess.run(command, capture_output=True, text=True, check=False)
    for line in finished.stdout.splitlines():
        log.info(line)
    for line in finished.stderr.splitlines():
        log.error(line)
    if finished.returncode == USAGE_OR_CONFIGURATION_ERROR:
        raise AirflowFailException(f"{command[0]} ended with exit status 2 (usage or config)")
    if finished.returncode != 0:
        raise JobFailedError(f"{command[0]} ended with exit status {finished.returncode}")


def report_final_failure(context: Context) -> None:
    """Failure callback: one JSON line once the task has failed for good (no retry left).

    Recording it in the run history (#32) and alerting on it (#43) build on this.
    """
    task_instance = context["ti"]
    error = context.get("exception")
    log.error(
        json.dumps(
            {
                "event": "task_failed",
                "dag_id": task_instance.dag_id,
                "task_id": task_instance.task_id,
                "run_id": task_instance.run_id,
                "try_number": task_instance.try_number,
                "error": type(error).__name__ if error else None,
                "message": str(error) if error else None,
            }
        )
    )
