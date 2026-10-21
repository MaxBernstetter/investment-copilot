"""Maps run alerts to the transparency ``Alert`` shape of the contracts."""

from contracts.transparency.v1 import Alert, AlertSeverity

from ingestion.application.alerts import RunAlert

MAX_CAUSE_LENGTH = 4000
"""The ``cause`` limit of the contract; longer causes are cut."""


def to_alert(alert: RunAlert) -> Alert:
    return Alert(
        alert_id=alert.alert_id,
        name=alert.name,
        severity=AlertSeverity(alert.severity.value),
        since=alert.since,
        cleared_at=alert.cleared_at,
        acknowledged_at=None,
        run_id=alert.run_id,
        attempt=alert.attempt,
        cause=alert.cause[:MAX_CAUSE_LENGTH],
    )
