from typing import Any

import pytest
from pydantic import ValidationError

from contracts.transparency.v1 import (
    ALERTS_PATH,
    RUN_PATH,
    RUNS_PATH,
    Alert,
    AlertSeverity,
    Run,
    RunStatus,
)


def finished_run(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "run_id": "daily_load_ecb-2026-10-16",
        "attempt": 1,
        "service": "ingestion",
        "operation": "daily",
        "status": "succeeded",
        "started_at": "2026-10-16T07:00:00Z",
        "finished_at": "2026-10-16T07:00:12Z",
        "duration_seconds": 12.0,
        "delivered_count": 121,
        "recorded_count": 121,
        "unchanged_count": 0,
        "error_type": None,
        "error_message": None,
    }
    return fields | overrides


def running_run(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "run_id": "daily_load_ecb-2026-10-16",
        "attempt": 1,
        "service": "ingestion",
        "operation": "daily",
        "status": "running",
        "started_at": "2026-10-16T07:00:00Z",
        "finished_at": None,
        "duration_seconds": None,
        "delivered_count": 0,
        "recorded_count": 0,
        "unchanged_count": 0,
        "error_type": None,
        "error_message": None,
    }
    return fields | overrides


def alert(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "alert_id": "ingestion-run_failed-daily_load_ecb-2026-10-16-1",
        "name": "run_failed",
        "severity": "critical",
        "since": "2026-10-16T07:00:12Z",
        "cleared_at": None,
        "acknowledged_at": None,
        "run_id": "daily_load_ecb-2026-10-16",
        "attempt": 1,
        "cause": "PersistenceWriteError: write rejected",
    }
    return fields | overrides


def test_run_statuses() -> None:
    assert {status.value for status in RunStatus} == {
        "running",
        "succeeded",
        "partial",
        "failed",
    }


def test_a_finished_run_round_trips_json() -> None:
    run = Run.model_validate(finished_run())

    assert run.status == RunStatus.SUCCEEDED
    assert Run.model_validate_json(run.model_dump_json()) == run


def test_a_running_run_has_no_finish_and_no_duration() -> None:
    run = Run.model_validate(running_run())

    assert run.finished_at is None
    assert run.duration_seconds is None


def test_a_running_run_with_a_finish_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Run.model_validate(running_run(finished_at="2026-10-16T07:00:12Z"))


def test_a_finished_run_without_a_finish_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Run.model_validate(finished_run(finished_at=None, duration_seconds=None))


def test_counts_are_not_negative() -> None:
    with pytest.raises(ValidationError):
        Run.model_validate(finished_run(delivered_count=-1))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Run.model_validate(finished_run(extra="not in the contract"))


def test_alert_severities() -> None:
    assert {severity.value for severity in AlertSeverity} == {"critical", "warning"}


def test_an_alert_round_trips_json() -> None:
    item = Alert.model_validate(alert())

    assert item.severity == AlertSeverity.CRITICAL
    assert Alert.model_validate_json(item.model_dump_json()) == item


def test_paths() -> None:
    assert RUNS_PATH == "/v1/runs"
    assert RUN_PATH == "/v1/runs/{run_id}"
    assert ALERTS_PATH == "/v1/alerts"
