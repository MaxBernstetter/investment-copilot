"""Run history reads: calls ``ing_run`` through python-oracledb (thin mode)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import oracledb

from ingestion.domain.run import Operation, RunAttempt, RunCounts, RunStatus


class OracleRunHistory:
    """Reads attempts through the ``ing_run`` package; each call uses one pooled connection."""

    def __init__(self, pool: oracledb.AsyncConnectionPool, *, call_timeout_ms: int) -> None:
        self._pool = pool
        self._call_timeout_ms = call_timeout_ms

    async def list_attempts(
        self,
        *,
        started_from: datetime | None,
        started_before: datetime | None,
        before_attempt_id: int | None,
        limit: int,
    ) -> Sequence[RunAttempt]:
        return await self._call(
            "ing.ing_run.get_runs",
            {
                "p_started_from": _naive_utc(started_from),
                "p_started_before": _naive_utc(started_before),
                "p_before_attempt_id": before_attempt_id,
                "p_limit": limit,
            },
        )

    async def get_attempts(self, run_id: str) -> Sequence[RunAttempt]:
        return await self._call("ing.ing_run.get_run", {"p_run_id": run_id})

    async def _call(self, function: str, parameters: dict[str, Any]) -> list[RunAttempt]:
        async with self._pool.acquire() as connection:
            connection.call_timeout = self._call_timeout_ms
            ref = await connection.cursor().callfunc(
                function, oracledb.DB_TYPE_CURSOR, keyword_parameters=parameters
            )
            rows = await ref.fetchall()
        return [_attempt(row) for row in rows]


def _naive_utc(moment: datetime | None) -> datetime | None:
    """Oracle ``timestamp`` columns hold UTC without a zone."""
    if moment is None:
        return None
    return moment.astimezone(UTC).replace(tzinfo=None)


def _aware_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC)


def _attempt(row: tuple[Any, ...]) -> RunAttempt:
    (
        attempt_id,
        run_id,
        attempt,
        operation,
        status,
        started_at,
        finished_at,
        delivered_count,
        recorded_count,
        unchanged_count,
        error_type,
        error_message,
    ) = row
    return RunAttempt(
        attempt_id=int(attempt_id),
        run_id=str(run_id),
        attempt=int(attempt),
        operation=Operation(operation),
        status=RunStatus(status),
        started_at=_aware_utc(started_at),
        finished_at=None if finished_at is None else _aware_utc(finished_at),
        counts=RunCounts(int(delivered_count), int(recorded_count), int(unchanged_count)),
        error_type=error_type,
        error_message=error_message,
    )
