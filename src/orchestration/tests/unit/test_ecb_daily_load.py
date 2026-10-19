import json
import logging
import sys
from datetime import date

import pytest
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

from orchestration.ecb_daily_load import (
    JobFailedError,
    daily_load_command,
    report_final_failure,
    run_job,
    valid_date_for,
)


def python_exiting(code: int, *, stdout: str = "", stderr: str = "") -> list[str]:
    """A stand-in for the ingestion job: prints, then exits with ``code``."""
    script = f"import sys; print({stdout!r}); print({stderr!r}, file=sys.stderr); sys.exit({code})"
    return [sys.executable, "-c", script]


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
) -> None:
    caplog.set_level(logging.INFO)

    run_job(python_exiting(0, stdout='{"event": "load_finished"}'))

    assert '{"event": "load_finished"}' in caplog.text


def test_a_failed_load_raises_an_error_that_airflow_retries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(JobFailedError, match="exit status 1") as raised:
        run_job(python_exiting(1, stderr='{"event": "load_failed"}'))

    assert not isinstance(raised.value, AirflowFailException)
    assert '{"event": "load_failed"}' in caplog.text


def test_a_usage_or_configuration_error_fails_without_retry() -> None:
    with pytest.raises(AirflowFailException, match="exit status 2"):
        run_job(python_exiting(2))


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
