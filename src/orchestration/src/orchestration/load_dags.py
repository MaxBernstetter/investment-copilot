"""Factories for the per-source load DAGs: a daily load and a manual backfill for each source.

A source's configuration is a ``LoadSource`` in ``orchestration.sources``. The DAG bodies are
the same for every source; the callbacks and the job steps are the shared ones in
``orchestration.ecb_daily_load``. The DAG files that call these factories are in ``dags/``.
See ``docs/project/00-data-ingestion/04-daily-schedule.md``.
"""

from datetime import date, timedelta

import pendulum
from airflow.sdk import DAG, CronTriggerTimetable, Param, dag, get_current_context, task

from orchestration.ecb_backfill import backfill_years, history_command
from orchestration.ecb_daily_load import (
    daily_load_command,
    mark_unfinished_attempt_failed,
    remember_run_id,
    report_final_failure,
    run_job,
    valid_date_for,
)
from orchestration.quality_check import daily_check_command, range_check_command
from orchestration.sources import LoadSource


def daily_run_id(dag_id: str, valid_date: date) -> str:
    return f"{dag_id}-{valid_date.isoformat()}"


def daily_check_run_id(dag_id: str, curve_id: str, valid_date: date) -> str:
    return f"{dag_id}-check-{curve_id}-{valid_date.isoformat()}"


def backfill_run_id(dag_id: str, start: date, end: date) -> str:
    return f"{dag_id}-{start.isoformat()}-{end.isoformat()}"


def backfill_check_run_id(dag_id: str, curve_id: str, start: date, end: date) -> str:
    return f"{dag_id}-check-{curve_id}-{start.isoformat()}-{end.isoformat()}"


def build_daily_load_dag(source: LoadSource) -> DAG:
    """The daily DAG ``daily_load_<source>``: load the previous publication day, then check it."""
    dag_id = f"daily_load_{source.source_id}"
    timezone = pendulum.timezone(source.timezone)

    @dag(
        dag_id=dag_id,
        schedule=CronTriggerTimetable(source.cron, timezone=timezone),
        start_date=source.start_date,
        catchup=False,
        max_active_runs=1,
        tags=["daily_load", source.source_id],
        default_args={"owner": "ingestion"},
    )
    def daily_load() -> None:
        @task(
            task_id=f"load_{source.source_id}",
            pool=source.pool,
            retries=2,
            retry_delay=timedelta(minutes=10),
            retry_exponential_backoff=2.0,
            execution_timeout=timedelta(minutes=30),
            on_failure_callback=[report_final_failure, mark_unfinished_attempt_failed],
            on_retry_callback=mark_unfinished_attempt_failed,
        )
        def load() -> None:
            context = get_current_context()
            run_at = context["logical_date"] or context["dag_run"].run_after
            valid_date = valid_date_for(run_at.astimezone(timezone).date(), source)
            run_id = daily_run_id(dag_id, valid_date)
            remember_run_id(context["ti"], run_id, source.source_id)
            run_job(daily_load_command(source.source_id, valid_date, run_id))

        @task(
            retries=2,
            retry_delay=timedelta(minutes=10),
            retry_exponential_backoff=2.0,
            execution_timeout=timedelta(minutes=30),
            on_failure_callback=report_final_failure,
        )
        def check_quality(curve_id: str) -> None:
            context = get_current_context()
            run_at = context["logical_date"] or context["dag_run"].run_after
            valid_date = valid_date_for(run_at.astimezone(timezone).date(), source)
            run_id = daily_check_run_id(dag_id, curve_id, valid_date)
            run_job(daily_check_command(curve_id, valid_date, run_id))

        load() >> check_quality.expand(curve_id=list(source.curve_ids))

    return daily_load()


def build_backfill_dag(source: LoadSource) -> DAG:
    """The manual DAG ``backfill_<source>``: load a date range one year at a time, then check."""
    dag_id = f"backfill_{source.source_id}"

    @dag(
        dag_id=dag_id,
        schedule=None,
        catchup=False,
        max_active_runs=1,
        params={
            "start": Param(type="string", format="date"),
            "end": Param(type="string", format="date"),
        },
        tags=["backfill", source.source_id],
        default_args={"owner": "ingestion"},
    )
    def backfill() -> None:
        @task
        def plan() -> list[dict[str, str]]:
            params = get_current_context()["params"]
            start = date.fromisoformat(params["start"])
            end = date.fromisoformat(params["end"])
            chunks = backfill_years(start, end)
            return [{"start": start.isoformat(), "end": end.isoformat()} for start, end in chunks]

        @task(
            pool=source.pool,
            max_active_tis_per_dag=1,
            retries=2,
            retry_delay=timedelta(minutes=10),
            retry_exponential_backoff=2.0,
            execution_timeout=timedelta(minutes=30),
            on_failure_callback=[report_final_failure, mark_unfinished_attempt_failed],
            on_retry_callback=mark_unfinished_attempt_failed,
        )
        def load_year(chunk: dict[str, str]) -> None:
            context = get_current_context()
            start = date.fromisoformat(chunk["start"])
            end = date.fromisoformat(chunk["end"])
            run_id = backfill_run_id(dag_id, start, end)
            remember_run_id(context["ti"], run_id, source.source_id)
            run_job(history_command(source.source_id, start, end, run_id))

        @task(
            retries=2,
            retry_delay=timedelta(minutes=10),
            retry_exponential_backoff=2.0,
            execution_timeout=timedelta(minutes=30),
            on_failure_callback=report_final_failure,
        )
        def check_year(chunk: dict[str, str], curve_id: str) -> None:
            start = date.fromisoformat(chunk["start"])
            end = date.fromisoformat(chunk["end"])
            run_id = backfill_check_run_id(dag_id, curve_id, start, end)
            run_job(range_check_command(curve_id, start, end, run_id))

        chunks = plan()
        load_year.expand(chunk=chunks) >> check_year.expand(
            chunk=chunks, curve_id=list(source.curve_ids)
        )

    return backfill()


__all__ = [
    "backfill_check_run_id",
    "backfill_run_id",
    "build_backfill_dag",
    "build_daily_load_dag",
    "daily_check_run_id",
    "daily_run_id",
]
