"""Ports of the processing use cases: read observations and store quality results."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from processing.application.alerts import LatestCheckRun
from processing.domain.assessment import QualityCheck
from processing.domain.check_run import CheckRunAttempt
from processing.domain.quality import Value


@dataclass(frozen=True, slots=True)
class Grid:
    maturities: tuple[str, ...]
    as_of: datetime


class ObservationReader(Protocol):
    async def grid(self, curve_id: str) -> Grid | None:
        """The curve grid and persistence knowledge time, or nothing if the curve is unknown."""

    async def series(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
    ) -> list[Value]:
        """One maturity between two valid dates as of a knowledge time."""


class QualityStore(Protocol):
    async def record(self, check: QualityCheck) -> None:
        """Persist one assessed chunk of a quality check run."""


class CheckRunReader(Protocol):
    async def latest_check_runs(self) -> list[LatestCheckRun]:
        """The latest check run of every curve that has one."""


class CheckRunHistory(Protocol):
    async def list_check_runs(
        self,
        *,
        recorded_from: datetime | None,
        recorded_before: datetime | None,
        before_check_run_id: int | None,
        limit: int,
    ) -> Sequence[CheckRunAttempt]:
        """Check runs newest first, with ``recorded_at`` in ``[recorded_from, recorded_before)``."""

    async def get_check_runs(self, run_id: str) -> Sequence[CheckRunAttempt]:
        """Every check run of one run id, in attempt order."""
