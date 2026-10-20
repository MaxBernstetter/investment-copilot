"""Daily load of the ECB euro area AAA spot curve.

Runs Monday to Friday at 13:15 Europe/Berlin, after the ECB publishes (about 12:00 CET
on TARGET business days), and loads the previous TARGET business day with the job's
lookback window. On a TARGET holiday the run is skipped. See
``docs/project/00-data-ingestion/04-daily-schedule.md``.
"""

from datetime import datetime, timedelta

import pendulum
from airflow.sdk import CronTriggerTimetable, dag, get_current_context, task

from orchestration.ecb_daily_load import (
    daily_load_command,
    mark_unfinished_attempt_failed,
    remember_run_id,
    report_final_failure,
    run_job,
    valid_date_for,
)
from orchestration.quality_check import daily_check_command

DAG_ID = "daily_load_ecb"
TIMEZONE = pendulum.timezone("Europe/Berlin")


@dag(
    dag_id=DAG_ID,
    schedule=CronTriggerTimetable("15 13 * * 1-5", timezone=TIMEZONE),
    start_date=datetime(2026, 10, 19, tzinfo=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    tags=["daily_load", "ecb"],
    default_args={"owner": "ingestion"},
)
def daily_load_ecb() -> None:
    @task(
        pool="ecb",
        retries=2,
        retry_delay=timedelta(minutes=10),
        retry_exponential_backoff=2.0,
        execution_timeout=timedelta(minutes=30),
        on_failure_callback=[report_final_failure, mark_unfinished_attempt_failed],
        on_retry_callback=mark_unfinished_attempt_failed,
    )
    def load_ecb() -> None:
        context = get_current_context()
        run_at = context["logical_date"] or context["dag_run"].run_after
        valid_date = valid_date_for(run_at.astimezone(TIMEZONE).date())
        run_id = f"{DAG_ID}-{valid_date.isoformat()}"
        remember_run_id(context["ti"], run_id)
        run_job(daily_load_command(valid_date, run_id))

    @task(
        retries=2,
        retry_delay=timedelta(minutes=10),
        retry_exponential_backoff=2.0,
        execution_timeout=timedelta(minutes=30),
        on_failure_callback=report_final_failure,
    )
    def check_quality() -> None:
        context = get_current_context()
        run_at = context["logical_date"] or context["dag_run"].run_after
        valid_date = valid_date_for(run_at.astimezone(TIMEZONE).date())
        run_job(daily_check_command(valid_date, f"{DAG_ID}-check-{valid_date.isoformat()}"))

    load_ecb() >> check_quality()


daily_load_ecb()
