import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import oracledb

from ingestion.infrastructure.ing.pool import OracleHealth


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


class ErrorPool:
    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[FakeConnection]:
        raise oracledb.DatabaseError("connection failed")
        yield FakeConnection()


def test_health_check_sets_the_call_timeout_and_answers() -> None:
    pool = FakePool()
    health = OracleHealth(cast(oracledb.AsyncConnectionPool, pool), call_timeout_ms=2_500)

    assert asyncio.run(health.is_reachable()) is True
    assert pool.connection.call_timeout == 2_500


def test_health_check_returns_false_when_oracle_errors() -> None:
    health = OracleHealth(cast(oracledb.AsyncConnectionPool, ErrorPool()), call_timeout_ms=1_000)

    assert asyncio.run(health.is_reachable()) is False
