"""Run alerts: an operation whose latest attempts failed stays alerted until its next success.

An alert is an episode. For each operation and each rule, the episode is the run of attempts
with the rule's status after the operation's last success. The next success clears it.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from ingestion.domain.run import Operation, RunAttempt, RunStatus

RUN_FAILED = "run_failed"
RUN_PARTIAL = "run_partial"
CLEARED_WINDOW = timedelta(days=7)
"""Alerts cleared longer ago than this are no longer listed."""


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"


_RULES: tuple[tuple[str, RunStatus, Severity], ...] = (
    (RUN_FAILED, RunStatus.FAILED, Severity.CRITICAL),
    (RUN_PARTIAL, RunStatus.PARTIAL, Severity.WARNING),
)


@dataclass(frozen=True, slots=True)
class RunAlert:
    alert_id: str
    """``f"{name}-{first_attempt_id}"``: stable while the alert is active, new after a clear."""
    name: str
    severity: Severity
    operation: Operation
    since: datetime
    """``finished_at`` of the episode's first failing attempt."""
    cleared_at: datetime | None
    """``finished_at`` of the success that cleared the episode; ``None`` while active."""
    run_id: str
    """Pointers come from the episode's latest failing attempt."""
    attempt: int
    cause: str


class RunAlertReader(Protocol):
    async def alert_attempts(self, *, cleared_after: datetime) -> Sequence[RunAttempt]:
        """Finished attempts after the last success of each operation, in attempt order."""
        ...


def run_alerts(attempts: Sequence[RunAttempt], *, now: datetime) -> list[RunAlert]:
    """Alerts of the episodes that are active or were cleared within ``CLEARED_WINDOW``."""
    by_operation: dict[Operation, list[RunAttempt]] = defaultdict(list)
    for attempt in sorted(attempts, key=lambda row: row.attempt_id):
        by_operation[attempt.operation].append(attempt)

    cutoff = now - CLEARED_WINDOW
    alerts = [
        alert
        for operation, rows in by_operation.items()
        for name, status, severity in _RULES
        for alert in _episodes(rows, name, status, severity, operation)
        if alert.cleared_at is None or alert.cleared_at >= cutoff
    ]
    return sorted(alerts, key=lambda alert: alert.since, reverse=True)


def _episodes(
    rows: Sequence[RunAttempt],
    name: str,
    status: RunStatus,
    severity: Severity,
    operation: Operation,
) -> list[RunAlert]:
    """Episodes of one rule within one operation; ``rows`` are in attempt order."""
    episodes: list[RunAlert] = []
    first: RunAttempt | None = None
    since: datetime | None = None
    latest: RunAttempt | None = None
    for row in rows:
        if row.finished_at is None:
            continue
        if row.status is RunStatus.SUCCEEDED:
            if first is not None and latest is not None and since is not None:
                episodes.append(_alert(name, severity, operation, first, since, latest, row))
            first = since = latest = None
        elif row.status is status:
            if first is None:
                first, since = row, row.finished_at
            latest = row
    if first is not None and latest is not None and since is not None:
        episodes.append(_alert(name, severity, operation, first, since, latest, None))
    return episodes


def _alert(
    name: str,
    severity: Severity,
    operation: Operation,
    first: RunAttempt,
    since: datetime,
    latest: RunAttempt,
    clearing: RunAttempt | None,
) -> RunAlert:
    return RunAlert(
        alert_id=f"{name}-{first.attempt_id}",
        name=name,
        severity=severity,
        operation=operation,
        since=since,
        cleared_at=None if clearing is None else clearing.finished_at,
        run_id=latest.run_id,
        attempt=latest.attempt,
        cause=_cause(latest),
    )


def _cause(attempt: RunAttempt) -> str:
    error_type = attempt.error_type or ""
    if attempt.error_message is None:
        return error_type
    return f"{error_type}: {attempt.error_message}"


async def current_run_alerts(reader: RunAlertReader, *, now: datetime) -> list[RunAlert]:
    """Active alerts and alerts cleared within ``CLEARED_WINDOW`` of ``now``."""
    attempts = await reader.alert_attempts(cleared_after=now - CLEARED_WINDOW)
    return run_alerts(attempts, now=now)
