import re

import oracledb
import pytest

from tests.integration.conftest import OracleDatabase


def test_creates_the_observation_table_partitioned_by_valid_date(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            select t.partitioning_type, k.column_name, t.interval
              from user_part_tables t
              join user_part_key_columns k on k.name = t.table_name
             where t.table_name = 'OBSERVATION'
            """
        )
        assert cursor.fetchall() == [("RANGE", "VALID_DATE", "NUMTOYMINTERVAL(1, 'MONTH')")]


def test_compiles_the_core_observation_package(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select object_type, status from user_objects"
            " where object_name = 'CORE_OBSERVATION' order by object_type"
        )
        assert cursor.fetchall() == [("PACKAGE", "VALID"), ("PACKAGE BODY", "VALID")]


def test_reapplying_the_migrations_changes_nothing(oracle: OracleDatabase) -> None:
    output = oracle.migrate()

    assert re.findall(r"Run:\s+(\d+)", output) == ["0", "0"]


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from core.observation",
        "delete from core.observation",
    ],
)
def test_the_service_user_cannot_touch_the_table_directly(
    oracle: OracleDatabase, statement: str
) -> None:
    with (
        oracle.connect_as_app() as connection,
        connection.cursor() as cursor,
        pytest.raises(oracledb.DatabaseError, match="ORA-00942"),
    ):
        cursor.execute(statement)
