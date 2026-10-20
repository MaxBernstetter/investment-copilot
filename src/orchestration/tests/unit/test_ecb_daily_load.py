import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

from orchestration.ecb_daily_load import (
    JobFailedError,
    daily_load_command,
    report_final_failure,
    run_job,
    valid_date_for,
)


@pytest.fixture
def job_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YIELDLENS_INGESTION_JOB_IMAGE", "yieldlens-ingestion:local")
    monkeypatch.setenv("YIELDLENS_DOCKER_NETWORK", "yieldlens-dev_default")


@contextmanager
def mock_container_run(exit_code: int, *, stdout: str = "", stderr: str = "") -> Iterator[Any]:
    def side_effect(command: list[str]) -> None:
        if stdout:
            logging.getLogger("orchestration.job_runner").info(stdout)
        if stderr:
            logging.getLogger("orchestration.job_runner").error(stderr)
        if exit_code == 2:
            raise AirflowFailException(f"{command[0]} ended with exit status 2 (usage or config)")
        if exit_code != 0:
            raise JobFailedError(f"{command[0]} ended with exit status {exit_code}")

    with patch("orchestration.ecb_daily_load.run_job_container", side_effect=side_effect) as mocked:
        yield mocked


@pytest.mark.parametrize(
    ("run_day", "valid_date"),
    [
        (date(2026, 10, 14), date(2026, 10, 13)),  # Wednesday loads Tuesday
        (date(2026, 10, 19), date(2026, 10, 16)),  # Monday loads Friday
        (date(2026, 4, 7), date(2026, 4, 2)),  # Tuesday after Easter loads Maundy Thursday
    ],
)
def test_a_run_loads_the_previous_target_business_day(run_day: date, valid_date: date) -> None:
    assert valid_date_for(run_day) == valid_date


@pytest.mark.parametrize(
    "run_day",
    [date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 12, 25)],
    ids=["good-friday", "easter-monday", "labour-day", "christmas"],
)
def test_a_run_on_a_target_holiday_is_skipped(run_day: date) -> None:
    with pytest.raises(AirflowSkipException, match="TARGET holiday"):
        valid_date_for(run_day)


def test_the_daily_command_names_the_valid_date_and_the_run_id() -> None:
    assert daily_load_command(date(2026, 10, 16), "daily_load_ecb-2026-10-16") == [
        "ingestion-load-ecb",
        "daily",
        "--valid-date",
        "2026-10-16",
        "--run-id",
        "daily_load_ecb-2026-10-16",
    ]


def test_a_finished_job_passes_and_its_summary_reaches_the_task_log(
    caplog: pytest.LogCaptureFixture,
    job_env: None,
) -> None:
    caplog.set_level(logging.INFO, logger="orchestration.job_runner")
    with mock_container_run(0, stdout='{"event": "load_finished"}'):
        run_job(
            [
                "ingestion-load-ecb",
                "daily",
                "--valid-date",
                "2026-10-16",
                "--run-id",
                "x",
            ]
        )

    assert '{"event": "load_finished"}' in caplog.text


def test_a_failed_load_raises_an_error_that_airflow_retries(
    caplog: pytest.LogCaptureFixture,
    job_env: None,
) -> None:
    caplog.set_level(logging.ERROR, logger="orchestration.job_runner")
    with (
        mock_container_run(1, stderr='{"event": "load_failed"}'),
        pytest.raises(JobFailedError, match="exit status 1") as raised,
    ):
        run_job(["ingestion-load-ecb", "daily"])

    assert not isinstance(raised.value, AirflowFailException)
    assert '{"event": "load_failed"}' in caplog.text


def test_a_usage_or_configuration_error_fails_without_retry(job_env: None) -> None:
    with mock_container_run(2), pytest.raises(AirflowFailException, match="exit status 2"):
        run_job(["ingestion-load-ecb", "daily"])


def test_a_final_failure_is_logged_as_one_json_line(caplog: pytest.LogCaptureFixture) -> None:
    class FakeTaskInstance:
        dag_id = "daily_load_ecb"
        task_id = "load_ecb"
        run_id = "scheduled__2026-10-19T11:15:00+00:00"
        try_number = 3

    report_final_failure(
        {"ti": FakeTaskInstance(), "exception": JobFailedError("ingestion job ended with exit 1")}  # type: ignore[typeddict-item]
    )

    [record] = caplog.records
    assert record.levelno == logging.ERROR
    assert json.loads(record.getMessage()) == {
        "event": "task_failed",
        "dag_id": "daily_load_ecb",
        "task_id": "load_ecb",
        "run_id": "scheduled__2026-10-19T11:15:00+00:00",
        "try_number": 3,
        "error": "JobFailedError",
        "message": "ingestion job ended with exit 1",
    }


def test_the_failure_callback_does_not_raise_on_broken_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    report_final_failure({})
    assert "task_failed callback could not log structured failure" in caplog.text
