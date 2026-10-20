"""Use case: read published values and assess their quality in bounded chunks."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from processing.application.ports import ObservationReader, QualityStore
from processing.domain.assessment import QualityCheck, assess
from processing.domain.quality import Rule, Severity, Status, Value
from processing.domain.rule_config import THRESHOLDS_BY_CURVE

CHUNK_DAYS = 366
LEAD_IN_DAYS = 31


class UnknownCurveError(LookupError):
    """The curve has no configured quality thresholds."""


@dataclass(frozen=True, slots=True)
class FindingCount:
    rule: Rule
    severity: Severity
    count: int


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
    worst_status: Status
    finding_counts: tuple[FindingCount, ...]


def _worst_day_status(checks: list[QualityCheck]) -> Status:
    statuses = {day.status for check in checks for day in check.days}
    if Status.WARN in statuses:
        return Status.WARN
    if Status.INFO in statuses:
        return Status.INFO
    return Status.PASSED


def _finding_counts(checks: list[QualityCheck]) -> tuple[FindingCount, ...]:
    counts = Counter(
        (finding.rule, finding.severity) for check in checks for finding in check.findings
    )
    ordered = sorted(counts.items(), key=lambda item: (item[0][0].value, item[0][1].value))
    return tuple(
        FindingCount(rule=rule, severity=severity, count=count)
        for (rule, severity), count in ordered
    )


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
        checked_as_of = grid_read.as_of if grid_read is not None else None
        checks: list[QualityCheck] = []

        if grid_read is not None:
            as_of = grid_read.as_of
            maturities = grid_read.maturities
            chunk_start = valid_from
            while chunk_start <= valid_to:
                chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), valid_to)
                series_from = chunk_start - timedelta(days=LEAD_IN_DAYS)
                series: dict[str, list[Value]] = {}
                for maturity in maturities:
                    series[maturity] = await self._reader.series(
                        curve_id, maturity, series_from, chunk_end, as_of
                    )

                check = assess(
                    run_id=run_id,
                    curve_id=curve_id,
                    valid_from=chunk_start,
                    valid_to=chunk_end,
                    checked_as_of=as_of,
                    grid=maturities,
                    series=series,
                    thresholds=thresholds,
                )
                await self._store.record(check)
                checks.append(check)

                chunk_start = chunk_end + timedelta(days=1)

        return CheckSummary(
            curve_id=curve_id,
            run_id=run_id,
            checked_as_of=checked_as_of,
            chunks=len(checks),
            days=sum(len(check.days) for check in checks),
            values=sum(len(check.values) for check in checks),
            warn_count=sum(
                1
                for check in checks
                for finding in check.findings
                if finding.severity is Severity.WARN
            ),
            info_count=sum(
                1
                for check in checks
                for finding in check.findings
                if finding.severity is Severity.INFO
            ),
            worst_status=_worst_day_status(checks),
            finding_counts=_finding_counts(checks),
        )
