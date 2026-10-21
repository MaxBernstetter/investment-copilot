import asyncio
import dataclasses
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, Tracer, format_trace_id
from pydantic import SecretStr

from processing.config import DatabaseSettings
from processing.domain.assessment import DayStatus, QualityCheck, ValueStatus
from processing.domain.check_run import CheckRunAttempt
from processing.domain.quality import Finding, Rule, Severity, Status
from processing.domain.rule_config import RULE_SET_VERSION
from processing.infrastructure.proc import OracleQualityStore, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

CURVE_ID = "ecb-aaa-spot-sim"
RUN_ID = "check-quality-ecb-aaa-spot-sim-2026-10-05-2026-10-08"
CHECKED_AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
VALID_FROM = date(2026, 10, 6)
VALID_TO = date(2026, 10, 8)
OCT_07 = date(2026, 10, 7)


def as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


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
                OCT_07,
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


_NOOP_TRACER = trace.NoOpTracer()


async def _with_store[T](
    oracle: OracleDatabase,
    action: Callable[[OracleQualityStore], Awaitable[T]],
    *,
    tracer: Tracer = _NOOP_TRACER,
) -> T:
    pool = create_pool(
        DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD)),
    )
    store = OracleQualityStore(pool, call_timeout_ms=30_000, tracer=tracer)
    try:
        return await action(store)
    finally:
        await pool.close()


def record(oracle: OracleDatabase, check: QualityCheck) -> None:
    async def action(store: OracleQualityStore) -> None:
        await store.record(check)

    asyncio.run(_with_store(oracle, action))


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
        assert as_date(run_row[2]) == VALID_FROM
        assert as_date(run_row[3]) == VALID_TO
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
        day_rows = [(as_date(row[0]), row[1]) for row in cursor.fetchall()]
        assert day_rows == [
            (VALID_FROM, "passed"),
            (OCT_07, "warn"),
            (VALID_TO, "warn"),
        ]

        cursor.execute(
            "select version_id, maturity, valid_date, status from value_quality"
            " where check_run_id = :id order by valid_date, maturity",
            [check_run_id],
        )
        value_rows = [(row[0], row[1], as_date(row[2]), row[3]) for row in cursor.fetchall()]
        assert value_rows == [
            (1, "10Y", VALID_FROM, "passed"),
            (2, "10Y", VALID_TO, "warn"),
        ]

        cursor.execute(
            "select rule, severity, valid_date, maturity from quality_finding"
            " where check_run_id = :id order by valid_date, rule",
            [check_run_id],
        )
        finding_rows = [(row[0], row[1], as_date(row[2]), row[3]) for row in cursor.fetchall()]
        assert finding_rows == [
            ("missing-maturity", "warn", OCT_07, "10Y"),
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


def test_value_statuses_come_from_the_latest_check_known_at_as_of(
    oracle: OracleDatabase,
) -> None:
    early = CHECKED_AS_OF
    later = CHECKED_AS_OF + timedelta(hours=1)
    record(oracle, sample_check(checked_as_of=early))
    record(
        oracle,
        QualityCheck(
            run_id=RUN_ID,
            curve_id=CURVE_ID,
            valid_from=VALID_FROM,
            valid_to=VALID_TO,
            checked_as_of=later,
            rule_set_version=RULE_SET_VERSION,
            days=(
                DayStatus(VALID_FROM, Status.PASSED),
                DayStatus(OCT_07, Status.WARN),
                DayStatus(VALID_TO, Status.PASSED),
            ),
            values=(
                ValueStatus(1, "10Y", VALID_FROM, Status.PASSED),
                ValueStatus(2, "10Y", VALID_TO, Status.PASSED),
            ),
            findings=(),
        ),
    )

    async def read() -> None:
        between = early + timedelta(minutes=30)

        async def at_between(store: OracleQualityStore) -> list[ValueStatus]:
            return await store.value_statuses(CURVE_ID, VALID_TO, VALID_TO, between)

        async def at_later_time(store: OracleQualityStore) -> list[ValueStatus]:
            return await store.value_statuses(CURVE_ID, VALID_TO, VALID_TO, later)

        assert await _with_store(oracle, at_between) == [
            ValueStatus(2, "10Y", VALID_TO, Status.WARN)
        ]
        assert await _with_store(oracle, at_later_time) == [
            ValueStatus(2, "10Y", VALID_TO, Status.PASSED)
        ]

    asyncio.run(read())


def test_findings_filter_by_maturity(oracle: OracleDatabase) -> None:
    record(oracle, sample_check())

    async def read() -> None:
        async def all_for_day(store: OracleQualityStore) -> list[Finding]:
            return await store.findings(CURVE_ID, OCT_07, OCT_07, CHECKED_AS_OF)

        async def ten_year_only(store: OracleQualityStore) -> list[Finding]:
            return await store.findings(CURVE_ID, OCT_07, OCT_07, CHECKED_AS_OF, maturity="10Y")

        all_findings = await _with_store(oracle, all_for_day)
        ten_year = await _with_store(oracle, ten_year_only)
        assert len(all_findings) == 1
        assert all_findings[0].maturity == "10Y"
        assert ten_year == all_findings

    asyncio.run(read())


def test_oracle_session_carries_the_trace_id(oracle: OracleDatabase) -> None:
    spans = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(spans))
    tracer = provider.get_tracer("test")
    run_id = f"otel-{uuid.uuid4().hex}"

    async def action(store: OracleQualityStore) -> tuple[str, str, str]:
        with tracer.start_as_current_span("root") as root:
            await store.record(sample_check(run_id=run_id))
            async with store._session("probe") as connection:
                cursor = connection.cursor()
                await cursor.execute(
                    "select sys_context('USERENV','CLIENT_IDENTIFIER'),"
                    " sys_context('USERENV','CLIENT_INFO') from dual"
                )
                row = await cursor.fetchone()
        trace_id = format_trace_id(root.get_span_context().trace_id)
        return str(row[0]), str(row[1]), trace_id

    client_identifier, client_info, trace_id = asyncio.run(
        _with_store(oracle, action, tracer=tracer)
    )

    assert client_identifier == trace_id
    assert client_info == trace_id
    names = {span.name for span in spans.get_finished_spans() if span.kind is SpanKind.CLIENT}
    assert "proc_quality.record_check" in names


def fresh_curve() -> str:
    return f"proc-{uuid.uuid4().hex[:16]}"


def check_run_ids(oracle: OracleDatabase, run_id: str) -> list[int]:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select check_run_id from check_run where run_id = :run_id order by check_run_id",
            [run_id],
        )
        return [int(row[0]) for row in cursor.fetchall()]


def set_recorded_at(oracle: OracleDatabase, check_run_id: int, moment: datetime) -> None:
    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute(
            "update check_run set recorded_at = :moment where check_run_id = :id",
            moment=moment.astimezone(UTC).replace(tzinfo=None),
            id=check_run_id,
        )
        connection.commit()


def list_check_runs(
    oracle: OracleDatabase,
    *,
    recorded_from: datetime | None = None,
    recorded_before: datetime | None = None,
    before_check_run_id: int | None = None,
    limit: int = 50,
) -> list[CheckRunAttempt]:
    async def action(store: OracleQualityStore) -> list[CheckRunAttempt]:
        return list(
            await store.list_check_runs(
                recorded_from=recorded_from,
                recorded_before=recorded_before,
                before_check_run_id=before_check_run_id,
                limit=limit,
            )
        )

    return asyncio.run(_with_store(oracle, action))


def get_check_runs(oracle: OracleDatabase, run_id: str) -> list[CheckRunAttempt]:
    async def action(store: OracleQualityStore) -> list[CheckRunAttempt]:
        return list(await store.get_check_runs(run_id))

    return asyncio.run(_with_store(oracle, action))


def test_record_stores_the_value_count(oracle: OracleDatabase) -> None:
    run_id = f"count-{uuid.uuid4().hex}"
    record(oracle, sample_check(run_id=run_id))
    record(
        oracle,
        dataclasses.replace(sample_check(run_id=run_id), values=(sample_check().values[0],)),
    )

    with oracle.connect_as_owner() as connection, connection.cursor() as cursor:
        cursor.execute("select value_count from check_run where run_id = :run_id", [run_id])
        assert cursor.fetchone()[0] == 1


def test_check_runs_are_newest_first_and_page_by_check_run_id(oracle: OracleDatabase) -> None:
    curve_id = fresh_curve()
    run_ids = [f"paging-{uuid.uuid4().hex}" for _ in range(3)]
    for hour, run_id in enumerate(run_ids):
        record(
            oracle,
            dataclasses.replace(
                sample_check(run_id=run_id, checked_as_of=CHECKED_AS_OF + timedelta(hours=hour)),
                curve_id=curve_id,
            ),
        )
    ids = [check_run_ids(oracle, run_id)[0] for run_id in run_ids]
    window_start = datetime(2080, 1, 1, tzinfo=UTC)
    for check_run_id in ids:
        set_recorded_at(oracle, check_run_id, window_start + timedelta(hours=1))
    window_end = window_start + timedelta(days=1)

    first_page = list_check_runs(
        oracle, recorded_from=window_start, recorded_before=window_end, limit=2
    )
    second_page = list_check_runs(
        oracle,
        recorded_from=window_start,
        recorded_before=window_end,
        before_check_run_id=ids[1],
        limit=2,
    )

    assert [row.check_run_id for row in first_page] == [ids[2], ids[1]]
    assert [row.run_id for row in first_page] == [run_ids[2], run_ids[1]]
    assert [row.check_run_id for row in second_page] == [ids[0]]


def test_check_runs_filter_on_recorded_at(oracle: OracleDatabase) -> None:
    curve_id = fresh_curve()
    early_run, late_run = f"early-{uuid.uuid4().hex}", f"late-{uuid.uuid4().hex}"
    record(oracle, dataclasses.replace(sample_check(run_id=early_run), curve_id=curve_id))
    record(
        oracle,
        dataclasses.replace(
            sample_check(run_id=late_run, checked_as_of=CHECKED_AS_OF + timedelta(hours=1)),
            curve_id=curve_id,
        ),
    )
    early_moment = datetime(2081, 6, 1, 10, 0, tzinfo=UTC)
    late_moment = datetime(2081, 6, 3, 10, 0, tzinfo=UTC)
    set_recorded_at(oracle, check_run_ids(oracle, early_run)[0], early_moment)
    set_recorded_at(oracle, check_run_ids(oracle, late_run)[0], late_moment)

    only_early = list_check_runs(
        oracle,
        recorded_from=datetime(2081, 6, 1, tzinfo=UTC),
        recorded_before=datetime(2081, 6, 2, tzinfo=UTC),
        limit=10,
    )
    only_late = list_check_runs(
        oracle,
        recorded_from=datetime(2081, 6, 2, tzinfo=UTC),
        recorded_before=datetime(2081, 6, 4, tzinfo=UTC),
        limit=10,
    )

    assert [row.run_id for row in only_early] == [early_run]
    assert only_early[0].recorded_at == early_moment
    assert [row.run_id for row in only_late] == [late_run]


def test_a_run_returns_its_check_runs_numbered_by_recorded_at(oracle: OracleDatabase) -> None:
    run_id = f"chunks-{uuid.uuid4().hex}"
    record(oracle, sample_check(run_id=run_id, checked_as_of=CHECKED_AS_OF))
    record(oracle, sample_check(run_id=run_id, checked_as_of=CHECKED_AS_OF + timedelta(hours=1)))
    first_recorded, second_recorded = check_run_ids(oracle, run_id)
    # The second chunk was recorded later but carries the earlier recorded_at, so it is attempt 1.
    set_recorded_at(oracle, first_recorded, datetime(2082, 1, 2, tzinfo=UTC))
    set_recorded_at(oracle, second_recorded, datetime(2082, 1, 1, tzinfo=UTC))

    attempts = get_check_runs(oracle, run_id)

    assert attempts == [
        CheckRunAttempt(
            check_run_id=second_recorded,
            run_id=run_id,
            attempt=1,
            recorded_at=datetime(2082, 1, 1, tzinfo=UTC),
            value_count=2,
        ),
        CheckRunAttempt(
            check_run_id=first_recorded,
            run_id=run_id,
            attempt=2,
            recorded_at=datetime(2082, 1, 2, tzinfo=UTC),
            value_count=2,
        ),
    ]


def test_an_unknown_run_has_no_check_runs(oracle: OracleDatabase) -> None:
    assert get_check_runs(oracle, f"unknown-{uuid.uuid4().hex}") == []
