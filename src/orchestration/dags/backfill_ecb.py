"""Manual backfill of the ECB euro area AAA spot curve over a date range.

Triggered by hand with the ``start`` and ``end`` parameters (inclusive dates). The range is
loaded one calendar year at a time, in the ``ecb`` pool, so it never runs next to the daily
load. Rerunning a range is safe: stored values are unchanged, so persistence keeps them as
they are. See ``docs/project/00-data-ingestion/04-daily-schedule.md``.
"""

from datetime import date, timedelta

from airflow.sdk import Param, dag, get_current_context, task

from orchestration.ecb_backfill import backfill_years, history_command
from orchestration.ecb_daily_load import report_final_failure, run_job
from orchestration.quality_check import range_check_command

DAG_ID = "backfill_ecb"


@dag(
    dag_id=DAG_ID,
    schedule=None,
    catchup=False,
    max_active_runs=1,
    params={
        "start": Param(type="string", format="date"),
        "end": Param(type="string", format="date"),
    },
    tags=["backfill", "ecb"],
    default_args={"owner": "ingestion"},
)
def backfill_ecb() -> None:
    @task
    def plan() -> list[dict[str, str]]:
        params = get_current_context()["params"]
        start = date.fromisoformat(params["start"])
        end = date.fromisoformat(params["end"])
        chunks = backfill_years(start, end)
        return [{"start": start.isoformat(), "end": end.isoformat()} for start, end in chunks]

    @task(
        pool="ecb",
        max_active_tis_per_dag=1,
        retries=2,
        retry_delay=timedelta(minutes=10),
        retry_exponential_backoff=2.0,
        execution_timeout=timedelta(minutes=30),
        on_failure_callback=report_final_failure,
    )
    def load_year(chunk: dict[str, str]) -> None:
        start = date.fromisoformat(chunk["start"])
        end = date.fromisoformat(chunk["end"])
        run_job(history_command(start, end, f"{DAG_ID}-{start.isoformat()}-{end.isoformat()}"))

    @task(
        retries=2,
        retry_delay=timedelta(minutes=10),
        retry_exponential_backoff=2.0,
        execution_timeout=timedelta(minutes=30),
        on_failure_callback=report_final_failure,
    )
    def check_year(chunk: dict[str, str]) -> None:
        start = date.fromisoformat(chunk["start"])
        end = date.fromisoformat(chunk["end"])
        run_job(
            range_check_command(start, end, f"{DAG_ID}-check-{start.isoformat()}-{end.isoformat()}")
        )

    chunks = plan()
    load_year.expand(chunk=chunks) >> check_year.expand(chunk=chunks)


backfill_ecb()
