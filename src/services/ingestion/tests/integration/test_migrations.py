import re
from datetime import datetime

import oracledb
import pytest

from tests.integration.conftest import OracleDatabase


def test_creates_the_delivery_table_partitioned_by_fetch_time(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            select t.partitioning_type, k.column_name, t.interval
              from user_part_tables t
              join user_part_key_columns k on k.name = t.table_name
             where t.table_name = 'DELIVERY'
            """
        )
        assert cursor.fetchall() == [("RANGE", "FETCHED_AT", "NUMTOYMINTERVAL(1, 'MONTH')")]


def test_compiles_the_ing_delivery_package(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select object_type, status from user_objects"
            " where object_name = 'ING_DELIVERY' order by object_type"
        )
        assert cursor.fetchall() == [("PACKAGE", "VALID"), ("PACKAGE BODY", "VALID")]


def test_compiles_the_ing_run_package(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select object_type, status from user_objects"
            " where object_name = 'ING_RUN' order by object_type"
        )
        assert cursor.fetchall() == [("PACKAGE", "VALID"), ("PACKAGE BODY", "VALID")]


def test_reapplying_the_migrations_changes_nothing(oracle: OracleDatabase) -> None:
    output = oracle.migrate()

    assert re.findall(r"Run:\s+(\d+)", output) == ["0", "0"]


def test_the_service_user_records_a_delivery_through_the_package(oracle: OracleDatabase) -> None:
    with oracle.connect_as_app() as connection, connection.cursor() as cursor:
        delivery_id = cursor.callfunc(
            "ing.ing_delivery.record_delivery",
            oracledb.DB_TYPE_NUMBER,
            keyword_parameters={
                "p_source_id": "ecb",
                "p_run_id": "it-run",
                "p_request_url": "https://data-api.ecb.europa.eu/service/data/YC/x",
                "p_response_status": 404,
                "p_fetched_at": datetime(2026, 3, 12, 18, 0),
            },
        )
        connection.commit()

        assert delivery_id > 0


def test_the_service_user_starts_a_run_through_the_package(oracle: OracleDatabase) -> None:
    with oracle.connect_as_app() as connection, connection.cursor() as cursor:
        attempt = cursor.callfunc(
            "ing.ing_run.start_run",
            oracledb.DB_TYPE_NUMBER,
            ["it-migrations-run", "daily"],
        )
        connection.commit()

    assert attempt == 1


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from ing.delivery",
        "delete from ing.delivery",
        "select count(*) from ing.run",
        "delete from ing.run",
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
