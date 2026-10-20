"""Run history reads against the ING schema in Oracle Free, seeded through OracleRunLog."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import oracledb
import pytest
from pydantic import SecretStr

from ingestion.config import DatabaseSettings
from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunOutcome, RunStatus
from ingestion.infrastructure.ing import OracleRunHistory, OracleRunLog, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def history_of(oracle: OracleDatabase) -> AsyncIterator[OracleRunHistory]:
    settings = DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD))
    pool: oracledb.AsyncConnectionPool = create_pool(settings)
    try:
        yield OracleRunHistory(pool, call_timeout_ms=settings.call_timeout_ms)
    finally:
        await pool.close()


def settings(oracle: OracleDatabase) -> DatabaseSettings:
    return DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD))


async def record(oracle: OracleDatabase, run_id: str, operation: Operation, count: int) -> None:
    """Records ``count`` attempts of ``run_id``, each finished as succeeded."""
    async with OracleRunLog(settings(oracle)) as runs:
        for _ in range(count):
            attempt = await runs.start(run_id, operation)
            await runs.finish(run_id, attempt, RunOutcome(RunStatus.SUCCEEDED, RunCounts(2, 1, 1)))


async def test_attempts_are_newest_first_and_page_by_attempt_id(oracle: OracleDatabase) -> None:
    await record(oracle, "it-history-page-a", Operation.DAILY, 2)
    await record(oracle, "it-history-page-b", Operation.DAILY, 1)

    async with history_of(oracle) as history:
        newest = await history.list_attempts(
            started_from=None, started_before=None, before_attempt_id=None, limit=2
        )
        a_first = await history.get_attempts("it-history-page-a")
        a_second = a_first[1]
        page = await history.list_attempts(
            started_from=None,
            started_before=None,
            before_attempt_id=a_second.attempt_id,
            limit=1,
        )

    assert [(row.run_id, row.attempt) for row in newest] == [
        ("it-history-page-b", 1),
        ("it-history-page-a", 2),
    ]
    assert [(row.run_id, row.attempt) for row in page] == [("it-history-page-a", 1)]


async def test_attempts_filter_on_started_at(oracle: OracleDatabase) -> None:
    await record(oracle, "it-history-filter", Operation.DAILY, 1)
    now = datetime.now(UTC)

    async with history_of(oracle) as history:
        later = await history.list_attempts(
            started_from=now + timedelta(days=1),
            started_before=None,
            before_attempt_id=None,
            limit=10,
        )
        before_2000 = await history.list_attempts(
            started_from=None,
            started_before=datetime(2000, 1, 1, tzinfo=UTC),
            before_attempt_id=None,
            limit=10,
        )

    assert later == []
    assert before_2000 == []


async def test_a_run_returns_every_attempt_in_order_with_utc_times(oracle: OracleDatabase) -> None:
    run_id = "it-history-run"
    before = datetime.now(UTC) - timedelta(seconds=5)
    await record(oracle, run_id, Operation.HISTORY, 2)

    async with history_of(oracle) as history:
        attempts: list[RunAttempt] = list(await history.get_attempts(run_id))

    assert [row.attempt for row in attempts] == [1, 2]
    for row in attempts:
        assert row.operation == Operation.HISTORY
        assert row.status == RunStatus.SUCCEEDED
        assert row.counts == RunCounts(2, 1, 1)
        assert row.started_at.tzinfo == UTC
        assert row.finished_at is not None
        assert row.finished_at.tzinfo == UTC
        assert row.started_at >= before
        assert row.started_at <= row.finished_at


async def test_an_unknown_run_has_no_attempts(oracle: OracleDatabase) -> None:
    async with history_of(oracle) as history:
        attempts = await history.get_attempts("it-history-no-such-run")

    assert list(attempts) == []
