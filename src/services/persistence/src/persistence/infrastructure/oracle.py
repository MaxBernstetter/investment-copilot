"""Oracle adapter: calls the CORE PL/SQL interface through python-oracledb (thin mode).

The service never writes tables directly; it only calls the core_observation
package, as the least-privilege user that has EXECUTE on it and nothing else.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import oracledb

from persistence.domain.observation import (
    InvalidObservationsError,
    Observation,
    OpenVersionExistsError,
    RecordedVersions,
)

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
        versions.append(version)
    return versions


def _error_code(error: oracledb.DatabaseError) -> int | None:
    (detail,) = error.args
    return getattr(detail, "code", None)


def _as_utc(timestamp: datetime) -> datetime:
    """CORE stores knowledge time as a plain TIMESTAMP in UTC."""
    return timestamp.replace(tzinfo=UTC)
