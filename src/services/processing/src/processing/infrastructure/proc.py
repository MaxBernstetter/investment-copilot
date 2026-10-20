"""Oracle adapter: the connection pool of the PROC schema and its health check."""

from datetime import UTC, datetime

import oracledb

from processing.config import DatabaseSettings
from processing.domain.assessment import DayStatus, QualityCheck, ValueStatus
from processing.domain.quality import Finding


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


class OracleQualityStore:
    def __init__(self, pool: oracledb.AsyncConnectionPool, *, call_timeout_ms: int) -> None:
        self._pool = pool
        self._call_timeout_ms = call_timeout_ms

    async def record(self, check: QualityCheck) -> None:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            days = await _day_status_list(connection, check.days)
            values = await _value_status_list(connection, check.values)
            findings = await _finding_list(connection, check.findings)
            cursor = connection.cursor()
            checked_as_of = _bind_timestamp(cursor, check.checked_as_of)
            check_run_id = cursor.var(oracledb.DB_TYPE_NUMBER)
            await cursor.callproc(
                "proc.proc_quality.record_check",
                [
                    check.run_id,
                    check.curve_id,
                    check.valid_from,
                    check.valid_to,
                    checked_as_of,
                    check.rule_set_version,
                    days,
                    values,
                    findings,
                    check_run_id,
                ],
            )
            await connection.commit()


async def _day_status_list(
    connection: oracledb.AsyncConnection, days: tuple[DayStatus, ...]
) -> oracledb.DbObject:
    list_type = await connection.gettype("PROC.PROC_DAY_STATUS_LIST_T")
    row_type = list_type.element_type
    batch: oracledb.DbObject = list_type.newobject()
    for day in days:
        row = row_type.newobject()
        row.VALID_DATE = day.valid_date
        row.STATUS = day.status.value
        batch.append(row)
    return batch


async def _value_status_list(
    connection: oracledb.AsyncConnection, values: tuple[ValueStatus, ...]
) -> oracledb.DbObject:
    list_type = await connection.gettype("PROC.PROC_VALUE_STATUS_LIST_T")
    row_type = list_type.element_type
    batch: oracledb.DbObject = list_type.newobject()
    for value in values:
        row = row_type.newobject()
        row.VERSION_ID = value.version_id
        row.MATURITY = value.maturity
        row.VALID_DATE = value.valid_date
        row.STATUS = value.status.value
        batch.append(row)
    return batch


async def _finding_list(
    connection: oracledb.AsyncConnection, findings: tuple[Finding, ...]
) -> oracledb.DbObject:
    list_type = await connection.gettype("PROC.PROC_FINDING_LIST_T")
    row_type = list_type.element_type
    batch: oracledb.DbObject = list_type.newobject()
    for finding in findings:
        row = row_type.newobject()
        row.VALID_DATE = finding.valid_date
        row.MATURITY = finding.maturity
        row.VERSION_ID = finding.version_id
        row.RULE = finding.rule.value
        row.SEVERITY = finding.severity.value
        row.VALUE = float(finding.value) if finding.value is not None else None
        row.EXPLANATION = finding.explanation
        row.EVIDENCE = finding.evidence
        batch.append(row)
    return batch


def _bind_timestamp(cursor: oracledb.AsyncCursor, timestamp: datetime) -> oracledb.Var:
    variable = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
    variable.setvalue(0, timestamp.astimezone(UTC).replace(tzinfo=None))
    return variable
