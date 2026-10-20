import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import SecretStr

from processing.config import DatabaseSettings
from processing.domain.assessment import DayStatus, QualityCheck, ValueStatus
from processing.domain.quality import Finding, Rule, Severity, Status
from processing.domain.rule_config import RULE_SET_VERSION
from processing.infrastructure.proc import OracleQualityStore, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

CURVE_ID = "ecb-aaa-spot-sim"
RUN_ID = "check-quality-ecb-aaa-spot-sim-2026-10-05-2026-10-08"
CHECKED_AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
VALID_FROM = date(2026, 10, 6)
VALID_TO = date(2026, 10, 8)


def sample_check(
    *,
    run_id: str = RUN_ID,
    checked_as_of: datetime = CHECKED_AS_OF,
) -> QualityCheck:
    return QualityCheck(
        run_id=run_id,
        curve_id=CURVE_ID,
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
        checked_as_of=checked_as_of,
        rule_set_version=RULE_SET_VERSION,
        days=(
            DayStatus(VALID_FROM, Status.PASSED),
            DayStatus(date(2026, 10, 7), Status.WARN),
            DayStatus(VALID_TO, Status.WARN),
        ),
        values=(
            ValueStatus(1, "10Y", VALID_FROM, Status.PASSED),
            ValueStatus(2, "10Y", VALID_TO, Status.WARN),
        ),
        findings=(
            Finding(
                Rule.MISSING_MATURITY,
                Severity.WARN,
                date(2026, 10, 7),
                "10Y",
                None,
                None,
                (
                    "No value for this maturity on a TARGET business day"
                    " on which other maturities have one."
                ),
                "No 10Y value on 2026-10-07",
            ),
            Finding(
                Rule.RANGE,
                Severity.WARN,
                VALID_TO,
                "10Y",
                2,
                Decimal("26.40"),
                "The value is outside the plausible range.",
                "26.40 % on 2026-10-08",
            ),
        ),
    )


def record(oracle: OracleDatabase, check: QualityCheck) -> None:
    async def store() -> None:
        pool = create_pool(
            DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD)),
        )
        try:
            await OracleQualityStore(pool, call_timeout_ms=30_000).record(check)
        finally:
            await pool.close()

    asyncio.run(store())


def table_counts(oracle: OracleDatabase) -> tuple[int, int, int, int]:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select count(*) from check_run")
        runs = int(cursor.fetchone()[0])
        cursor.execute("select count(*) from checked_day")
        days = int(cursor.fetchone()[0])
        cursor.execute("select count(*) from value_quality")
        values = int(cursor.fetchone()[0])
        cursor.execute("select count(*) from quality_finding")
        findings = int(cursor.fetchone()[0])
    return runs, days, values, findings


def test_record_stores_the_run_days_values_and_findings(oracle: OracleDatabase) -> None:
    check = sample_check()

    record(oracle, check)

    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select run_id, curve_id, valid_from, valid_to, checked_as_of, rule_set_version"
            " from check_run where curve_id = :curve_id",
            [CURVE_ID],
        )
        run_row = cursor.fetchone()
        assert run_row is not None
        assert run_row[0] == RUN_ID
        assert run_row[1] == CURVE_ID
        assert run_row[2] == VALID_FROM
        assert run_row[3] == VALID_TO
        assert run_row[4].replace(tzinfo=UTC) == CHECKED_AS_OF
        assert run_row[5] == RULE_SET_VERSION
        cursor.execute(
            "select check_run_id from check_run where curve_id = :curve_id",
            [CURVE_ID],
        )
        check_run_id = cursor.fetchone()[0]

        cursor.execute(
            "select valid_date, status from checked_day"
            " where check_run_id = :id order by valid_date",
            [check_run_id],
        )
        assert cursor.fetchall() == [
            (VALID_FROM, "passed"),
            (date(2026, 10, 7), "warn"),
            (VALID_TO, "warn"),
        ]

        cursor.execute(
            "select version_id, maturity, valid_date, status from value_quality"
            " where check_run_id = :id order by valid_date, maturity",
            [check_run_id],
        )
        assert cursor.fetchall() == [
            (1, "10Y", VALID_FROM, "passed"),
            (2, "10Y", VALID_TO, "warn"),
        ]

        cursor.execute(
            "select rule, severity, valid_date, maturity from quality_finding"
            " where check_run_id = :id order by valid_date, rule",
            [check_run_id],
        )
        assert cursor.fetchall() == [
            ("missing-maturity", "warn", date(2026, 10, 7), "10Y"),
            ("range", "warn", VALID_TO, "10Y"),
        ]


def test_recording_the_same_check_twice_keeps_one_run(oracle: OracleDatabase) -> None:
    check = sample_check()
    record(oracle, check)
    before = table_counts(oracle)

    record(oracle, sample_check(run_id="check-quality-rerun"))

    after = table_counts(oracle)
    assert after == before

    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select run_id from check_run where curve_id = :curve_id", [CURVE_ID])
        assert cursor.fetchone()[0] == "check-quality-rerun"


def test_a_later_knowledge_time_adds_a_new_run(oracle: OracleDatabase) -> None:
    record(oracle, sample_check())
    before_runs, _, _, _ = table_counts(oracle)

    later = CHECKED_AS_OF + timedelta(hours=1)
    record(oracle, sample_check(checked_as_of=later))

    after_runs, after_days, after_values, after_findings = table_counts(oracle)
    assert after_runs == before_runs + 1
    assert after_days == before_runs * 3 + 3
    assert after_values == before_runs * 2 + 2
    assert after_findings == before_runs * 2 + 2
