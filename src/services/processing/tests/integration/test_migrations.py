import asyncio
import re

import oracledb
import pytest
from pydantic import SecretStr

from processing.config import DatabaseSettings
from processing.infrastructure.proc import OracleHealth, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

RUN_COUNT = re.compile(r"Run:\s+(\d+)")


def test_migrations_apply_and_reapply_cleanly(oracle: OracleDatabase) -> None:
    applied = RUN_COUNT.findall(oracle.migration_output)
    assert len(applied) == 2
    assert all(int(count) > 0 for count in applied)

    assert RUN_COUNT.findall(oracle.migrate()) == ["0", "0"]


def test_the_app_user_has_only_create_session(oracle: OracleDatabase) -> None:
    with oracle.connect_as_app() as connection, connection.cursor() as cursor:
        cursor.execute("select privilege from session_privs")
        session_privileges = {row[0] for row in cursor.fetchall()}
        # The default INHERIT PRIVILEGES entry on the user itself belongs to PUBLIC,
        # so it is not something proc_app received: only rows granted to proc_app count.
        cursor.execute(
            "select privilege, owner || '.' || table_name from user_tab_privs"
            " where grantee = 'PROC_APP'"
        )
        granted_to_app = cursor.fetchall()

    assert session_privileges == {"CREATE SESSION"}
    assert granted_to_app == []


def test_the_app_user_cannot_read_the_tables(oracle: OracleDatabase) -> None:
    with (
        oracle.connect_as_app() as connection,
        connection.cursor() as cursor,
        pytest.raises(oracledb.DatabaseError, match="ORA-00942"),
    ):
        cursor.execute("select count(*) from proc.check_run")


def test_ready_against_the_migrated_database(oracle: OracleDatabase) -> None:
    async def probe() -> bool:
        pool = create_pool(
            DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD)),
        )
        try:
            return await OracleHealth(pool, call_timeout_ms=5_000).is_reachable()
        finally:
            await pool.close()

    assert asyncio.run(probe()) is True
