"""DAG integrity and the daily ECB schedule, from the DAG files as Airflow parses them."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pendulum
import pytest
from airflow.dag_processing.dagbag import DagBag
from airflow.sdk import DAG
from airflow.serialization.decoders import decode_timetable
from airflow.serialization.encoders import encode_timetable
from airflow.timetables.base import DataInterval, TimeRestriction

from orchestration.ecb_daily_load import report_final_failure

COMPONENT = Path(__file__).parents[2]
BERLIN = pendulum.timezone("Europe/Berlin")


@pytest.fixture(scope="module")
def pools() -> dict[str, dict[str, object]]:
    pools: dict[str, dict[str, object]] = json.loads((COMPONENT / "pools.json").read_text())
    return pools


@pytest.fixture(scope="module")
def dag_bag(pools: dict[str, dict[str, object]]) -> DagBag:
    # With known_pools, a task in a pool that pools.json does not create is a DAG warning.
    return DagBag(dag_folder=COMPONENT / "dags", known_pools={"default_pool", *pools})


@pytest.fixture(scope="module")
def daily_load_ecb(dag_bag: DagBag) -> DAG:
    dag = dag_bag.dags["daily_load_ecb"]
    assert isinstance(dag, DAG)
    return dag


@pytest.fixture(scope="module")
def backfill_ecb(dag_bag: DagBag) -> DAG:
    dag = dag_bag.dags["backfill_ecb"]
    assert isinstance(dag, DAG)
    return dag


def test_every_dag_imports_uses_known_pools_and_has_an_owner_and_tags(dag_bag: DagBag) -> None:
    assert dag_bag.import_errors == {}
    assert dag_bag.dag_warnings == set()
    assert dag_bag.dags
    for dag in dag_bag.dags.values():
        assert dag.tags, dag.dag_id
        assert all(task.owner != "airflow" for task in dag.tasks), dag.dag_id


def test_the_ecb_load_runs_monday_to_friday_at_13_15_in_berlin(daily_load_ecb: DAG) -> None:
    timetable = decode_timetable(encode_timetable(daily_load_ecb.timetable))
    monday = pendulum.datetime(2026, 10, 19, tz=BERLIN)  # summer time ends on Sunday 25 October
    restriction = TimeRestriction(earliest=monday, latest=None, catchup=True)

    runs: list[datetime] = []
    last: DataInterval | None = None
    for _ in range(6):
        info = timetable.next_dagrun_info(
            last_automated_data_interval=last, restriction=restriction
        )
        assert info is not None
        assert info.logical_date is not None
        runs.append(info.logical_date)
        last = info.data_interval

    assert [run.astimezone(BERLIN).replace(tzinfo=None) for run in runs] == [
        datetime(2026, 10, day, 13, 15) for day in (19, 20, 21, 22, 23, 26)
    ]


def test_one_run_at_a_time_and_no_catchup(daily_load_ecb: DAG) -> None:
    assert daily_load_ecb.max_active_runs == 1
    assert not daily_load_ecb.catchup


def test_the_load_retries_at_most_twice_and_reports_its_final_failure(
    daily_load_ecb: DAG,
) -> None:
    load = daily_load_ecb.get_task("load_ecb")

    assert load.retries == 2
    assert load.retry_delay == timedelta(minutes=10)
    assert load.on_failure_callback == [report_final_failure]


def test_the_load_runs_in_the_ecb_pool_of_size_one(
    daily_load_ecb: DAG, pools: dict[str, dict[str, object]]
) -> None:
    assert daily_load_ecb.get_task("load_ecb").pool == "ecb"
    assert pools["ecb"]["slots"] == 1


def test_the_backfill_is_manual_and_loads_one_year_at_a_time_in_the_ecb_pool(
    backfill_ecb: DAG, pools: dict[str, dict[str, object]]
) -> None:
    assert backfill_ecb.schedule is None
    assert backfill_ecb.max_active_runs == 1

    load = backfill_ecb.get_task("load_year")

    assert load.pool == "ecb"
    assert pools["ecb"]["slots"] == 1
    assert load.max_active_tis_per_dag == 1
    assert load.retries == 2
    assert load.on_failure_callback == report_final_failure


def test_the_daily_load_checks_quality_after_the_load(daily_load_ecb: DAG) -> None:
    check = daily_load_ecb.get_task("check_quality")

    assert set(check.upstream_task_ids) == {"load_ecb"}
    assert check.pool != "ecb"
    assert check.retries == 2
    assert check.retry_delay == timedelta(minutes=10)
    assert check.on_failure_callback == [report_final_failure]


def test_the_backfill_checks_each_year_after_the_loads(backfill_ecb: DAG) -> None:
    load = backfill_ecb.get_task("load_year")
    check = backfill_ecb.get_task("check_year")

    assert check in load.downstream_list
    assert check.pool != "ecb"
    assert check.retries == 2
    assert check.on_failure_callback == report_final_failure
