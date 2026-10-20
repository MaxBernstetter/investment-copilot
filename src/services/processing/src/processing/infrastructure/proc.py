"""Oracle adapter: the connection pool of the PROC schema and its health check."""

import oracledb

from processing.config import DatabaseSettings


def create_pool(settings: DatabaseSettings) -> oracledb.AsyncConnectionPool:
    return oracledb.create_pool_async(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password.get_secret_value(),
        min=settings.pool_min,
        max=settings.pool_max,
        increment=1,
        getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
        wait_timeout=settings.acquire_timeout_ms,
    )


class OracleHealth:
    def __init__(self, pool: oracledb.AsyncConnectionPool, *, call_timeout_ms: int) -> None:
        self._pool = pool
        self._call_timeout_ms = call_timeout_ms

    async def is_reachable(self) -> bool:
        try:
            async with self._pool.acquire() as connection:
                connection.call_timeout = self._call_timeout_ms
                cursor = connection.cursor()
                await cursor.execute("select 1 from dual")
                await cursor.fetchone()
        except oracledb.Error:
            return False
        return True
