"""Run history store: calls ``ing_run`` through python-oracledb (thin mode)."""

from types import TracebackType
from typing import Self

import oracledb

from ingestion.config import DatabaseSettings
from ingestion.domain.run import Operation, RunOutcome


class OracleRunLog:
    """One connection per job run. Use as an async context manager.

    Each call commits, so a running attempt is visible and its outcome survives a
    later crash.
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._connection: oracledb.AsyncConnection | None = None

    async def __aenter__(self) -> Self:
        self._connection = await oracledb.connect_async(
            dsn=self._settings.dsn,
            user=self._settings.user,
            password=self._settings.password.get_secret_value(),
        )
        self._connection.call_timeout = self._settings.call_timeout_ms
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def start(self, run_id: str, operation: Operation) -> int:
        connection = self._connected()
        attempt = await connection.cursor().callfunc(
            "ing.ing_run.start_run",
            int,
            [run_id, operation.value],
        )
        await connection.commit()
        return int(attempt)

    async def finish(self, run_id: str, attempt: int, outcome: RunOutcome) -> None:
        connection = self._connected()
        error_message = outcome.error_message
        if error_message is not None:
            error_message = error_message[:4000]
        await connection.cursor().callproc(
            "ing.ing_run.finish_run",
            keyword_parameters={
                "p_run_id": run_id,
                "p_attempt": attempt,
                "p_status": outcome.status.value,
                "p_delivered_count": outcome.counts.delivered_count,
                "p_recorded_count": outcome.counts.recorded_count,
                "p_unchanged_count": outcome.counts.unchanged_count,
                "p_error_type": outcome.error_type,
                "p_error_message": error_message,
            },
        )
        await connection.commit()

    def _connected(self) -> oracledb.AsyncConnection:
        if self._connection is None:
            raise RuntimeError("OracleRunLog is used outside its context")
        return self._connection
