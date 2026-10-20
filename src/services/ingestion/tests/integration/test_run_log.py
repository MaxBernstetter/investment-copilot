"""OracleRunLog against the ING schema in Oracle Free."""

import pytest

from ingestion.config import DatabaseSettings
from ingestion.domain.run import Operation, RunCounts, RunOutcome, RunStatus
from ingestion.infrastructure.ing import OracleRunLog
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

pytestmark = pytest.mark.anyio


def settings(oracle: OracleDatabase) -> DatabaseSettings:
    return DatabaseSettings.model_validate({"dsn": oracle.dsn, "password": APP_PASSWORD})


def read_attempt(oracle: OracleDatabase, run_id: str, attempt: int) -> dict[str, object]:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            select operation, status, delivered_count, recorded_count, unchanged_count,
                   error_type, error_message, length(error_message)
              from run where run_id = :run_id and attempt = :attempt
            """,
            run_id=run_id,
            attempt=attempt,
        )
        row = cursor.fetchone()
        assert row is not None
        return {
            "operation": row[0],
            "status": row[1],
            "delivered_count": row[2],
            "recorded_count": row[3],
            "unchanged_count": row[4],
            "error_type": row[5],
            "error_message": row[6],
            "error_message_length": row[7],
        }


async def test_start_numbers_the_attempts_of_a_run(oracle: OracleDatabase) -> None:
    run_id = "it-run-log-start"
    async with OracleRunLog(settings(oracle)) as runs:
        first = await runs.start(run_id, Operation.DAILY)
        second = await runs.start(run_id, Operation.DAILY)

    assert (first, second) == (1, 2)


async def test_finish_records_status_counts_and_error(oracle: OracleDatabase) -> None:
    run_id = "it-run-log-finish"
    outcome = RunOutcome(
        RunStatus.PARTIAL,
        RunCounts(66, 66, 0),
        "InvalidPayloadError",
        "bad csv",
    )
    async with OracleRunLog(settings(oracle)) as runs:
        attempt = await runs.start(run_id, Operation.HISTORY)
        await runs.finish(run_id, attempt, outcome)

    row = read_attempt(oracle, run_id, attempt)
    assert row["status"] == "partial"
    assert row["delivered_count"] == 66
    assert row["error_type"] == "InvalidPayloadError"


async def test_finish_twice_keeps_the_first_outcome(oracle: OracleDatabase) -> None:
    run_id = "it-run-log-idempotent"
    async with OracleRunLog(settings(oracle)) as runs:
        attempt = await runs.start(run_id, Operation.REPLAY)
        await runs.finish(
            run_id,
            attempt,
            RunOutcome(RunStatus.SUCCEEDED, RunCounts(1, 1, 0)),
        )
        await runs.finish(
            run_id,
            attempt,
            RunOutcome(RunStatus.FAILED, RunCounts(), "PersistenceWriteError", "nope"),
        )

    row = read_attempt(oracle, run_id, attempt)
    assert row["status"] == "succeeded"
    assert row["recorded_count"] == 1


async def test_a_long_error_message_is_cut_to_4000_characters(oracle: OracleDatabase) -> None:
    run_id = "it-run-log-truncate"
    message = "x" * 5000
    async with OracleRunLog(settings(oracle)) as runs:
        attempt = await runs.start(run_id, Operation.DAILY)
        await runs.finish(
            run_id,
            attempt,
            RunOutcome(RunStatus.FAILED, RunCounts(), "Boom", message),
        )

    row = read_attempt(oracle, run_id, attempt)
    assert row["error_message_length"] == 4000
    assert row["error_message"] == "x" * 4000
