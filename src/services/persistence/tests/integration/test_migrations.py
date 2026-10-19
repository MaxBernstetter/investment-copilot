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


def test_seeds_the_common_maturity_grid_as_version_1(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select maturity from grid_maturity where grid_version = 1 order by months")
        assert [maturity for (maturity,) in cursor] == [
            "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"
        ]  # fmt: skip


def test_records_the_ecb_curve_conventions_as_published(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select grid_version, rate_type, compounding, unit, source_model"
            " from curve where curve_id = 'ecb-aaa-spot'"
        )
        assert cursor.fetchall() == [(1, "spot", "continuous", "percent", "Svensson (ECB)")]


def test_defines_the_simulated_curve_apart_from_the_real_one(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select curve_id, simulated from curve"
            " where curve_id in ('ecb-aaa-spot', 'ecb-aaa-spot-sim') order by curve_id"
        )
        assert cursor.fetchall() == [("ecb-aaa-spot", "N"), ("ecb-aaa-spot-sim", "Y")]


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


def test_seeds_the_knowledge_clock_with_one_row(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select clock_id from knowledge_clock")
        assert [clock_id for (clock_id,) in cursor] == [1]
