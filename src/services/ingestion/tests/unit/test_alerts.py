"""Run alert episodes and the current-alerts use case against a stub history. No I/O."""

from datetime import UTC, datetime, timedelta

import pytest

from ingestion.application.alerts import (
    RUN_FAILED,
    RUN_PARTIAL,
    RunAlert,
    Severity,
    current_run_alerts,
    run_alerts,
)
from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunStatus
from tests.stub_run_history import StubRunHistory

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


def attempt(
    attempt_id: int,
    status: RunStatus,
    finished: datetime | None,
    *,
    operation: Operation = Operation.DAILY,
    number: int = 1,
    error_type: str | None = "SourceError",
    error_message: str | None = "boom",
) -> RunAttempt:
    started = NOW - timedelta(days=30)
    return RunAttempt(
        attempt_id=attempt_id,
        run_id=f"run-{attempt_id}",
        attempt=number,
        operation=operation,
        status=status,
        started_at=started,
        finished_at=finished,
        counts=RunCounts(),
        error_type=error_type if status in (RunStatus.FAILED, RunStatus.PARTIAL) else None,
        error_message=error_message if status in (RunStatus.FAILED, RunStatus.PARTIAL) else None,
    )


def by_name(alerts: list[RunAlert], name: str) -> list[RunAlert]:
    return [alert for alert in alerts if alert.name == name]


def test_a_failed_attempt_raises_an_active_critical_run_failed() -> None:
    finished = NOW - 2 * DAY

    alerts = run_alerts([attempt(1, RunStatus.FAILED, finished)], now=NOW)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.name == RUN_FAILED
    assert alert.severity is Severity.CRITICAL
    assert alert.cleared_at is None
    assert alert.cause == "SourceError: boom"
    assert alert.since == finished


def test_the_next_success_clears_it() -> None:
    cleared = NOW - DAY

    alerts = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 2 * DAY),
            attempt(2, RunStatus.SUCCEEDED, cleared),
        ],
        now=NOW,
    )

    assert len(alerts) == 1
    assert alerts[0].cleared_at == cleared


def test_a_partial_attempt_raises_a_warning_run_partial() -> None:
    alerts = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 3 * DAY),
            attempt(2, RunStatus.PARTIAL, NOW - DAY),
        ],
        now=NOW,
    )

    partial = by_name(alerts, RUN_PARTIAL)
    assert len(partial) == 1
    assert partial[0].severity is Severity.WARNING
    assert partial[0].cleared_at is None
    failed = by_name(alerts, RUN_FAILED)
    assert len(failed) == 1
    assert failed[0].cleared_at is None


def test_the_alert_id_stays_stable_while_failures_repeat() -> None:
    alerts = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 3 * DAY),
            attempt(2, RunStatus.FAILED, NOW - DAY, number=2, error_message="second"),
        ],
        now=NOW,
    )

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_id == "run_failed-1"
    assert alert.run_id == "run-2"
    assert alert.attempt == 2
    assert alert.cause == "SourceError: second"
    assert alert.since == NOW - 3 * DAY


def test_a_failure_after_a_clear_opens_a_new_alert_id() -> None:
    alerts = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 3 * DAY),
            attempt(2, RunStatus.SUCCEEDED, NOW - 2 * DAY),
            attempt(3, RunStatus.FAILED, NOW - DAY),
        ],
        now=NOW,
    )

    assert len(alerts) == 2
    newest, oldest = alerts
    assert newest.alert_id == "run_failed-3"
    assert newest.cleared_at is None
    assert oldest.alert_id == "run_failed-1"
    assert oldest.cleared_at == NOW - 2 * DAY


def test_alerts_cleared_more_than_seven_days_ago_are_dropped() -> None:
    old = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 10 * DAY),
            attempt(2, RunStatus.SUCCEEDED, NOW - 8 * DAY),
        ],
        now=NOW,
    )
    recent = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 10 * DAY),
            attempt(2, RunStatus.SUCCEEDED, NOW - 6 * DAY),
        ],
        now=NOW,
    )

    assert old == []
    assert len(recent) == 1
    assert recent[0].cleared_at == NOW - 6 * DAY


def test_operations_are_independent() -> None:
    alerts = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 2 * DAY, operation=Operation.DAILY),
            attempt(2, RunStatus.SUCCEEDED, NOW - DAY, operation=Operation.HISTORY),
        ],
        now=NOW,
    )

    assert len(alerts) == 1
    assert alerts[0].operation is Operation.DAILY
    assert alerts[0].cleared_at is None


def test_a_running_attempt_neither_raises_nor_clears() -> None:
    running_after_failure = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 2 * DAY),
            attempt(2, RunStatus.RUNNING, None),
        ],
        now=NOW,
    )
    running_after_success = run_alerts(
        [
            attempt(1, RunStatus.FAILED, NOW - 3 * DAY),
            attempt(2, RunStatus.SUCCEEDED, NOW - 2 * DAY),
            attempt(3, RunStatus.RUNNING, None),
        ],
        now=NOW,
    )
    running_alone = run_alerts([attempt(1, RunStatus.RUNNING, None)], now=NOW)

    assert len(running_after_failure) == 1
    assert running_after_failure[0].cleared_at is None
    assert len(running_after_success) == 1
    assert running_after_success[0].cleared_at == NOW - 2 * DAY
    assert running_alone == []


def test_cause_is_the_error_type_without_a_message() -> None:
    alerts = run_alerts(
        [attempt(1, RunStatus.FAILED, NOW - DAY, error_message=None)],
        now=NOW,
    )

    assert alerts[0].cause == "SourceError"


async def test_current_run_alerts_reads_from_seven_days_before_now() -> None:
    history = StubRunHistory(attempts=[attempt(1, RunStatus.FAILED, NOW - DAY)])

    alerts = await current_run_alerts(history, now=NOW)

    assert history.alert_calls == [NOW - timedelta(days=7)]
    assert [alert.name for alert in alerts] == [RUN_FAILED]
