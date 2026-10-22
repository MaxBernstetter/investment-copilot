"""Steps of the daily ECB load DAG: which date to load, how to run the job, what to report.

The load itself is the ingestion job ``ingestion-load-ecb`` (see
``docs/project/00-data-ingestion/03-ecb-load.md``). Its exit status decides the retry:
``0`` finished, ``1`` the load failed (retried by Airflow), ``2`` usage or configuration
error (a retry cannot help, so the task fails at once).
"""

import json
import logging
from collections.abc import Sequence
from datetime import date
from typing import Any

from airflow.sdk import Context
from airflow.sdk.exceptions import AirflowSkipException

from orchestration.job_runner import JobFailedError, run_job_container
from orchestration.target_calendar import is_target_business_day, previous_target_business_day

JOB_COMMAND = "ingestion-load-ecb"
RUN_ID_XCOM_KEY = "ingestion_run_id"
# The curves the ECB load writes, both from one request (see 01-data-sources); each is checked
# after each load.
CURVE_IDS = ("ecb-aaa-spot", "ecb-all-spot")

log = logging.getLogger(__name__)

__all__ = [
    "CURVE_IDS",
    "JOB_COMMAND",
    "RUN_ID_XCOM_KEY",
    "JobFailedError",
    "daily_load_command",
    "fail_unfinished_command",
    "mark_unfinished_attempt_failed",
    "remember_run_id",
    "report_final_failure",
    "run_job",
    "valid_date_for",
]


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


def remember_run_id(ti: Any, run_id: str) -> None:
    """Keeps the ingestion run id in XCom, so the failure callback can name the run."""
    ti.xcom_push(key=RUN_ID_XCOM_KEY, value=run_id)


def fail_unfinished_command(run_id: str, error_type: str, error_message: str | None) -> list[str]:
    command = [JOB_COMMAND, "fail-unfinished", "--run-id", run_id, "--error-type", error_type]
    if error_message is not None:
        command += ["--error-message", error_message]
    return command


def run_job(command: Sequence[str]) -> None:
    """Run the job in a container and map its exit status for Airflow retries."""
    run_job_container(command)


def mark_unfinished_attempt_failed(context: Context) -> None:
    """Retry and failure callback: marks this task's still running ingestion attempts failed.

    A task that Airflow kills (timeout, stop) never lets the job record its outcome, so the
    attempt would stay running. The callback runs the job's ``fail-unfinished`` command in
    Docker, the same way the load runs, so it does not depend on the ingestion REST API.
    It never raises: a failing callback must not hide the task's own failure.
    """
    try:
        ti = context["ti"]
        run_id = ti.xcom_pull(task_ids=ti.task_id, key=RUN_ID_XCOM_KEY, map_indexes=ti.map_index)
        if not run_id:
            log.info("fail_unfinished_skipped: no ingestion run id for task %s", ti.task_id)
            return
        exc = context.get("exception")
        error_type = type(exc).__name__ if exc else "AttemptNotFinished"
        error_message = (str(exc)[:500] or None) if exc else None
        run_job_container(fail_unfinished_command(run_id, error_type, error_message))
    except Exception:
        log.exception("fail_unfinished_failed: could not mark the ingestion attempt failed")


def report_final_failure(context: Context) -> None:
    """Failure callback: one JSON line once the task has failed for good (no retry left).

    The run history is recorded by ``mark_unfinished_attempt_failed``.
    """
    try:
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
    except Exception:
        log.exception("task_failed callback could not log structured failure")
