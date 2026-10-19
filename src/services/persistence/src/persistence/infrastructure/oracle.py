"""Oracle adapter: calls the CORE PL/SQL interface through python-oracledb (thin mode).

The service never writes tables directly; it only calls the core_observation
package, as the least-privilege user that has EXECUTE on it and nothing else.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime

import oracledb

from persistence.domain.curve import CurvePoint
from persistence.domain.observation import (
    InvalidObservationsError,
    Observation,
    OpenVersionExistsError,
    RecordedVersions,
)
from persistence.domain.series import SeriesPoint

OPEN_VERSION_EXISTS = 20001
"""Application error code of core_observation.open_version_exists (raised as ORA-20001)."""

DUPLICATE_OBSERVATION = 20002
"""Application error code of core_observation.duplicate_observation (raised as ORA-20002)."""

OFF_GRID_OBSERVATION = 20003
"""Application error code of core_observation.off_grid_observation (raised as ORA-20003)."""


def create_pool(
    *, dsn: str, user: str, password: str, min_size: int, max_size: int, acquire_timeout_ms: int
) -> oracledb.AsyncConnectionPool:
    return oracledb.create_pool_async(
        dsn=dsn,
        user=user,
        password=password,
        min=min_size,
        max=max_size,
        increment=1,
        getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
        wait_timeout=acquire_timeout_ms,
    )


class OracleObservationRepository:
    def __init__(self, pool: oracledb.AsyncConnectionPool, *, call_timeout_ms: int) -> None:
        self._pool = pool
        self._call_timeout_ms = call_timeout_ms

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            versions = await _version_list(connection, observations)
            cursor = connection.cursor()
            known_from = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
            recorded_count = cursor.var(oracledb.DB_TYPE_NUMBER)
            try:
                await cursor.callproc(
                    "core.core_observation.record_versions",
                    [versions, known_from, recorded_count],
                )
            except oracledb.DatabaseError as error:
                await connection.rollback()
                code = _error_code(error)
                if code == OPEN_VERSION_EXISTS:
                    raise OpenVersionExistsError(str(error)) from error
                if code in (DUPLICATE_OBSERVATION, OFF_GRID_OBSERVATION):
                    raise InvalidObservationsError(str(error)) from error
                raise
            await connection.commit()
        recorded = int(recorded_count.getvalue())
        return RecordedVersions(
            known_from=_as_utc(known_from.getvalue()),
            recorded_count=recorded,
            unchanged_count=len(observations) - recorded,
        )

    async def is_reachable(self) -> bool:
        try:
            async with self._pool.acquire() as connection:
                await connection.ping()
        except oracledb.Error:
            return False
        return True

    async def current_knowledge_time(self) -> datetime:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            now = await connection.cursor().callfunc(
                "core.core_observation.current_knowledge_time", oracledb.DB_TYPE_TIMESTAMP, []
            )
        return _as_utc(now)

    async def latest_valid_date(self, curve_id: str, as_of: datetime) -> date | None:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            cursor = connection.cursor()
            valid_date = await cursor.callfunc(
                "core.core_observation.latest_valid_date",
                oracledb.DB_TYPE_DATE,
                [curve_id, _bind_timestamp(cursor, as_of)],
            )
        return valid_date.date() if valid_date is not None else None

    async def points_as_of(
        self, curve_id: str, valid_date: date, as_of: datetime
    ) -> list[CurvePoint]:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            cursor = connection.cursor()
            points = await cursor.callfunc(
                "core.core_observation.get_as_of",
                oracledb.DB_TYPE_CURSOR,
                [curve_id, valid_date, _bind_timestamp(cursor, as_of)],
            )
            rows = await points.fetchall()
        return [
            CurvePoint(
                maturity=maturity,
                months=int(months),
                value=float(value) if value is not None else None,
            )
            for maturity, months, value in rows
        ]

    async def has_maturity(self, curve_id: str, maturity: str) -> bool:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            found = await connection.cursor().callfunc(
                "core.core_observation.has_maturity",
                oracledb.DB_TYPE_NUMBER,
                [curve_id, maturity],
            )
        return bool(found)

    async def series_as_of(
        self, curve_id: str, maturity: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[SeriesPoint]:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            cursor = connection.cursor()
            points = await cursor.callfunc(
                "core.core_observation.get_series",
                oracledb.DB_TYPE_CURSOR,
                [curve_id, maturity, valid_from, valid_to, _bind_timestamp(cursor, as_of)],
            )
            rows = await points.fetchall()
        return [
            SeriesPoint(valid_date=valid_date.date(), value=float(value))
            for valid_date, value in rows
        ]


async def _version_list(
    connection: oracledb.AsyncConnection, observations: Sequence[Observation]
) -> oracledb.DbObject:
    list_type = await connection.gettype("CORE.OBSERVATION_VERSION_LIST_T")
    version_type = list_type.element_type
    versions: oracledb.DbObject = list_type.newobject()
    for observation in observations:
        version = version_type.newobject()
        version.CURVE_ID = observation.curve_id
        version.MATURITY = observation.maturity
        version.VALID_DATE = observation.valid_date
        version.VALUE = observation.value
        version.ORIGIN = observation.origin.value
        version.METHOD_VERSION = observation.method_version
        version.SOURCE_ID = observation.source_id
        version.RUN_ID = observation.run_id
        version.CHANGE_REASON = observation.change_reason.value
        version.NORMALIZATION_VERSION = observation.normalization_version
        version.DELIVERY_ID = observation.delivery_id
        versions.append(version)
    return versions


def _error_code(error: oracledb.DatabaseError) -> int | None:
    (detail,) = error.args
    return getattr(detail, "code", None)


def _as_utc(timestamp: datetime) -> datetime:
    """CORE stores knowledge time as a plain TIMESTAMP in UTC."""
    return timestamp.replace(tzinfo=UTC)


def _bind_timestamp(cursor: oracledb.AsyncCursor, as_of: datetime) -> oracledb.Var:
    """Binds a knowledge time as a plain UTC TIMESTAMP, keeping its microseconds."""
    variable = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
    variable.setvalue(0, as_of.astimezone(UTC).replace(tzinfo=None))
    return variable
