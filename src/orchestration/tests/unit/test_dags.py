"""DAG integrity and the daily ECB schedule, from the DAG files as Airflow parses them."""

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

import pendulum
import pytest
from airflow.dag_processing.dagbag import DagBag
from airflow.sdk import DAG
from airflow.sdk.bases.decorator import DecoratedMappedOperator
from airflow.sdk.definitions._internal.expandinput import DictOfListsExpandInput
from airflow.serialization.decoders import decode_timetable
from airflow.serialization.encoders import encode_timetable
from airflow.serialization.enums import Encoding
from airflow.timetables.base import DataInterval, TimeRestriction

from orchestration.ecb_daily_load import (
    CURVE_IDS,
    mark_unfinished_attempt_failed,
    report_final_failure,
)
from orchestration.load_dags import build_backfill_dag, build_daily_load_dag
from orchestration.sources import ECB, SOURCES, LoadSource

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


def as_list(callbacks: object) -> list[object]:
    """Airflow keeps one callback as itself and several as a list; compare both alike."""
    return list(callbacks) if isinstance(callbacks, list) else [callbacks]


def mapped_arguments(dag: DAG, task_id: str) -> Mapping[str, object]:
    """The arguments a ``@task`` task is expanded over (its ``op_kwargs_expand_input``)."""
    task = dag.get_task(task_id)
    assert isinstance(task, DecoratedMappedOperator)
    expand = task.op_kwargs_expand_input
    assert isinstance(expand, DictOfListsExpandInput)
    return expand.value


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
    assert as_list(load.on_failure_callback) == [
        report_final_failure,
        mark_unfinished_attempt_failed,
    ]
    assert as_list(load.on_retry_callback) == [mark_unfinished_attempt_failed]


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
    assert as_list(load.on_failure_callback) == [
        report_final_failure,
        mark_unfinished_attempt_failed,
    ]
    assert as_list(load.on_retry_callback) == [mark_unfinished_attempt_failed]


def test_the_daily_load_checks_quality_after_the_load(daily_load_ecb: DAG) -> None:
    check = daily_load_ecb.get_task("check_quality")

    assert set(check.upstream_task_ids) == {"load_ecb"}
    assert check.pool != "ecb"
    assert check.retries == 2
    assert check.retry_delay == timedelta(minutes=10)
    assert as_list(check.on_failure_callback) == [report_final_failure]


def test_the_daily_load_checks_each_curve_the_load_writes(daily_load_ecb: DAG) -> None:
    assert mapped_arguments(daily_load_ecb, "check_quality") == {"curve_id": list(CURVE_IDS)}


def test_one_ecb_request_task_per_daily_run_whatever_the_curve_count(daily_load_ecb: DAG) -> None:
    assert [task.task_id for task in daily_load_ecb.tasks if task.pool == "ecb"] == ["load_ecb"]
    assert daily_load_ecb.get_task("load_ecb").retries == 2


def test_quality_checks_do_not_mark_ingestion_attempts(
    daily_load_ecb: DAG, backfill_ecb: DAG
) -> None:
    for check in (daily_load_ecb.get_task("check_quality"), backfill_ecb.get_task("check_year")):
        assert as_list(check.on_failure_callback) == [report_final_failure]
        assert as_list(check.on_retry_callback) == []


def test_the_backfill_checks_each_year_after_the_loads(backfill_ecb: DAG) -> None:
    load = backfill_ecb.get_task("load_year")
    check = backfill_ecb.get_task("check_year")

    assert check in load.downstream_list
    assert check.pool != "ecb"
    assert check.retries == 2
    assert as_list(check.on_failure_callback) == [report_final_failure]


def test_the_backfill_checks_each_curve_per_year(backfill_ecb: DAG) -> None:
    assert mapped_arguments(backfill_ecb, "check_year")["curve_id"] == list(CURVE_IDS)


def test_the_dag_bag_holds_exactly_one_daily_and_one_backfill_dag_per_source(
    dag_bag: DagBag,
) -> None:
    assert set(dag_bag.dags) == {
        *(f"daily_load_{source.source_id}" for source in SOURCES),
        *(f"backfill_{source.source_id}" for source in SOURCES),
    }
    assert set(dag_bag.dags) == {"daily_load_ecb", "backfill_ecb"}


@pytest.mark.parametrize("source", SOURCES, ids=lambda source: source.source_id)
def test_each_source_has_its_own_pool_of_size_one(
    source: LoadSource, dag_bag: DagBag, pools: dict[str, dict[str, object]]
) -> None:
    daily = dag_bag.dags[f"daily_load_{source.source_id}"]
    backfill = dag_bag.dags[f"backfill_{source.source_id}"]

    assert pools[source.pool]["slots"] == 1
    assert [task.task_id for task in daily.tasks if task.pool == source.pool] == [
        f"load_{source.source_id}"
    ]
    assert [task.task_id for task in backfill.tasks if task.pool == source.pool] == ["load_year"]
    assert {task.pool for task in (*daily.tasks, *backfill.tasks)} <= {
        "default_pool",
        source.pool,
    }


@pytest.mark.parametrize("source", SOURCES, ids=lambda source: source.source_id)
def test_each_dag_follows_its_source_config(source: LoadSource, dag_bag: DagBag) -> None:
    daily = dag_bag.dags[f"daily_load_{source.source_id}"]
    backfill = dag_bag.dags[f"backfill_{source.source_id}"]
    timetable = encode_timetable(daily.timetable)[Encoding.VAR]

    assert timetable["expression"] == source.cron
    assert timetable["timezone"] == source.timezone
    assert daily.start_date == source.start_date
    assert source.source_id in daily.tags
    assert source.source_id in backfill.tags
    assert mapped_arguments(daily, "check_quality") == {"curve_id": list(source.curve_ids)}
    assert mapped_arguments(backfill, "check_year")["curve_id"] == list(source.curve_ids)


def test_the_factory_makes_a_second_source_from_config_alone() -> None:
    ust = LoadSource(
        source_id="ust",
        curve_ids=("ust-par",),
        cron="0 8 * * 2-6",
        timezone="Europe/Berlin",
        start_date=datetime(2026, 10, 19, tzinfo=BERLIN),
        is_publication_day=lambda day: day.weekday() < 5,
        previous_publication_day=lambda day: day - timedelta(days=1),
        closed_message="{day} is a closed day for ust",
    )

    daily = build_daily_load_dag(ust)
    backfill = build_backfill_dag(ust)

    assert daily.dag_id == "daily_load_ust"
    assert backfill.dag_id == "backfill_ust"
    assert daily.get_task("load_ust").pool == "ust"
    assert backfill.get_task("load_year").pool == "ust"
    assert encode_timetable(daily.timetable)[Encoding.VAR]["expression"] == "0 8 * * 2-6"
    assert mapped_arguments(daily, "check_quality") == {"curve_id": ["ust-par"]}
    assert mapped_arguments(backfill, "check_year")["curve_id"] == ["ust-par"]
    assert ECB.pool == "ecb"
