"""Use case: read published values and assess their quality in bounded chunks."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from processing.application.ports import ObservationReader, QualityStore
from processing.domain.assessment import assess
from processing.domain.quality import Severity, Value
from processing.domain.rule_config import THRESHOLDS_BY_CURVE

CHUNK_DAYS = 366
LEAD_IN_DAYS = 31


class UnknownCurveError(LookupError):
    """The curve has no configured quality thresholds."""


@dataclass(frozen=True, slots=True)
class CheckSummary:
    curve_id: str
    run_id: str
    checked_as_of: datetime | None
    chunks: int
    days: int
    values: int
    warn_count: int
    info_count: int


class CheckQuality:
    """Loads observations from persistence and records quality assessments."""

    def __init__(self, reader: ObservationReader, store: QualityStore) -> None:
        self._reader = reader
        self._store = store

    async def __call__(
        self, curve_id: str, valid_from: date, valid_to: date, run_id: str
    ) -> CheckSummary:
        if curve_id not in THRESHOLDS_BY_CURVE:
            raise UnknownCurveError(curve_id)

        thresholds = THRESHOLDS_BY_CURVE[curve_id]
        grid_read = await self._reader.grid(curve_id)
        if grid_read is None:
            return CheckSummary(
                curve_id=curve_id,
                run_id=run_id,
                checked_as_of=None,
                chunks=0,
                days=0,
                values=0,
                warn_count=0,
                info_count=0,
            )

        checked_as_of = grid_read.as_of
        maturities = grid_read.maturities
        chunk_count = 0
        day_count = 0
        value_count = 0
        warn_count = 0
        info_count = 0

        chunk_start = valid_from
        while chunk_start <= valid_to:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), valid_to)
            series_from = chunk_start - timedelta(days=LEAD_IN_DAYS)
            series: dict[str, list[Value]] = {}
            for maturity in maturities:
                series[maturity] = await self._reader.series(
                    curve_id, maturity, series_from, chunk_end, checked_as_of
                )

            check = assess(
                run_id=run_id,
                curve_id=curve_id,
                valid_from=chunk_start,
                valid_to=chunk_end,
                checked_as_of=checked_as_of,
                grid=maturities,
                series=series,
                thresholds=thresholds,
            )
            await self._store.record(check)

            chunk_count += 1
            day_count += len(check.days)
            value_count += len(check.values)
            warn_count += sum(1 for finding in check.findings if finding.severity is Severity.WARN)
            info_count += sum(1 for finding in check.findings if finding.severity is Severity.INFO)

            chunk_start = chunk_end + timedelta(days=1)

        return CheckSummary(
            curve_id=curve_id,
            run_id=run_id,
            checked_as_of=checked_as_of,
            chunks=chunk_count,
            days=day_count,
            values=value_count,
            warn_count=warn_count,
            info_count=info_count,
        )
