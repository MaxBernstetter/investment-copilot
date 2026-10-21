"""Run alerts against the ING schema in Oracle Free: a failed replay alerts until it succeeds."""

from datetime import UTC, datetime

import pytest

from ingestion.application.alerts import RUN_FAILED, RunAlert, current_run_alerts
from ingestion.domain.run import Operation, RunCounts, RunOutcome, RunStatus
from ingestion.infrastructure.ing import OracleRunLog
from tests.integration.conftest import OracleDatabase
from tests.integration.test_run_history import history_of, settings

pytestmark = pytest.mark.anyio

RUN_ID = "it-alerts-replay"


def _replay_failure(alerts: list[RunAlert], *, alert_id: str | None = None) -> RunAlert:
    """The run_failed alert of the replay operation; by its run id or by its alert id."""
    if alert_id is None:
        matches = [
            alert
            for alert in alerts
            if alert.name == RUN_FAILED
            and alert.operation is Operation.REPLAY
            and alert.run_id == RUN_ID
        ]
    else:
        matches = [alert for alert in alerts if alert.alert_id == alert_id]
    assert len(matches) == 1
    return matches[0]


async def test_a_failed_replay_raises_an_alert_that_the_next_success_clears(
    oracle: OracleDatabase,
) -> None:
    async with OracleRunLog(settings(oracle)) as runs:
        failed = await runs.start(RUN_ID, Operation.REPLAY)
        await runs.finish(
            RUN_ID, failed, RunOutcome(RunStatus.FAILED, RunCounts(), "SourceError", "boom")
        )

    async with history_of(oracle) as history:
        active = _replay_failure(await current_run_alerts(history, now=datetime.now(UTC)))

        assert active.run_id == RUN_ID
        assert active.attempt == 1
        assert active.cleared_at is None
        assert active.cause == "SourceError: boom"

        async with OracleRunLog(settings(oracle)) as runs:
            succeeded = await runs.start(RUN_ID, Operation.REPLAY)
            await runs.finish(RUN_ID, succeeded, RunOutcome(RunStatus.SUCCEEDED, RunCounts()))

        cleared = _replay_failure(
            await current_run_alerts(history, now=datetime.now(UTC)),
            alert_id=active.alert_id,
        )

    assert cleared.cleared_at is not None
