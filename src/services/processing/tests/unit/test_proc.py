import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import oracledb

from processing.infrastructure.proc import OracleHealth


class FakeCursor:
    async def execute(self, sql: str) -> None:
        self.sql = sql

    async def fetchone(self) -> tuple[int]:
        return (1,)


class FakeConnection:
    call_timeout = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor()


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[FakeConnection]:
        yield self.connection


def test_health_check_sets_the_call_timeout_and_answers() -> None:
    pool = FakePool()
    health = OracleHealth(cast(oracledb.AsyncConnectionPool, pool), call_timeout_ms=2_500)

    assert asyncio.run(health.is_reachable()) is True
    assert pool.connection.call_timeout == 2_500
