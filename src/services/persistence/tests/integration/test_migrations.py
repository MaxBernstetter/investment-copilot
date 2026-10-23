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


def test_seeds_grid_version_2_as_grid_1_plus_the_short_tenors(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select maturity from grid_maturity where grid_version = 2 order by months")
        assert [maturity for (maturity,) in cursor] == [
            "1M", "1.5M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y",
            "7Y", "10Y", "15Y", "20Y", "30Y",
        ]  # fmt: skip


def test_stores_months_as_number_5_2(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select data_precision, data_scale from user_tab_columns"
            " where table_name = 'GRID_MATURITY' and column_name = 'MONTHS'"
        )
        assert cursor.fetchall() == [(5, 2)]
        cursor.execute(
            "select months from grid_maturity where grid_version = 2 and maturity = '1.5M'"
        )
        assert cursor.fetchall() == [(1.5,)]


def test_grid_version_1_is_unchanged_by_grid_2(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select maturity, months from grid_maturity where grid_version = 1 order by months"
        )
        assert cursor.fetchall() == [
            ("3M", 3), ("6M", 6), ("1Y", 12), ("2Y", 24), ("3Y", 36), ("5Y", 60),
            ("7Y", 84), ("10Y", 120), ("15Y", 180), ("20Y", 240), ("30Y", 360),
        ]  # fmt: skip
        cursor.execute(
            "select curve_id, grid_version from curve"
            " where curve_id in ('ecb-aaa-spot', 'ecb-aaa-spot-sim', 'ecb-all-spot')"
            " order by curve_id"
        )
        assert cursor.fetchall() == [
            ("ecb-aaa-spot", 1), ("ecb-aaa-spot-sim", 1), ("ecb-all-spot", 1),
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


def test_records_the_catalogue_entries_of_the_ecb_curves(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select curve_id, label, source_id, area, attribution from curve"
            " where curve_id in ('ecb-aaa-spot', 'ecb-aaa-spot-sim') order by curve_id"
        )
        assert cursor.fetchall() == [
            (
                "ecb-aaa-spot",
                "ECB euro area AAA spot",
                "ecb",
                "Euro area",
                "Source: ECB statistics",
            ),
            (
                "ecb-aaa-spot-sim",
                "ECB euro area AAA spot (scenario data)",
                "scenario",
                "Euro area",
                "Simulated scenario based on ECB statistics",
            ),
        ]


def test_defines_the_ecb_all_issuer_curve_with_the_aaa_conventions(
    oracle: OracleDatabase,
) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select grid_version, rate_type, compounding, unit, source_model, simulated"
            " from curve where curve_id = 'ecb-all-spot'"
        )
        assert cursor.fetchall() == [(1, "spot", "continuous", "percent", "Svensson (ECB)", "N")]


def test_records_the_catalogue_entry_of_the_ecb_all_issuer_curve(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select label, source_id, area, attribution from curve where curve_id = 'ecb-all-spot'"
        )
        assert cursor.fetchall() == [
            ("ECB euro area all-issuer spot", "ecb", "Euro area", "Source: ECB statistics")
        ]


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


def test_defines_the_us_treasury_par_curve_on_grid_2(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select grid_version, rate_type, compounding, unit, source_model, simulated"
            " from curve where curve_id = 'ust-par'"
        )
        assert cursor.fetchall() == [(2, "par", "semi-annual", "percent", None, "N")]


def test_records_the_catalogue_entry_of_the_us_treasury_par_curve(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select label, source_id, area, attribution from curve where curve_id = 'ust-par'"
        )
        assert cursor.fetchall() == [
            (
                "US Treasury par",
                "ust",
                "United States",
                "Source: U.S. Department of the Treasury",
            )
        ]


def test_the_existing_curves_keep_their_grid_and_conventions(oracle: OracleDatabase) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select curve_id, grid_version, rate_type, compounding from curve"
            " where curve_id in ('ecb-aaa-spot', 'ecb-aaa-spot-sim', 'ecb-all-spot')"
            " order by curve_id"
        )
        assert cursor.fetchall() == [
            ("ecb-aaa-spot", 1, "spot", "continuous"),
            ("ecb-aaa-spot-sim", 1, "spot", "continuous"),
            ("ecb-all-spot", 1, "spot", "continuous"),
        ]
