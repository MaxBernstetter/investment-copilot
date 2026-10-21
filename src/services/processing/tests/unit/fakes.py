from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from processing.domain.assessment import CheckedDay, ValueStatus
from processing.domain.check_run import CheckRunAttempt
from processing.domain.quality import Finding, Rule, Severity, Status
from processing.infrastructure.telemetry import Telemetry, setup_telemetry

AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
FROM = date(2026, 10, 7)
TO = date(2026, 10, 7)


class RecordingMetricExporter(MetricExporter):
    """Keeps every exported batch of metrics; the job's reader exports only at shutdown here."""

    def __init__(self) -> None:
        super().__init__()
        self.exported: list[MetricsData] = []

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs: object
    ) -> MetricExportResult:
        self.exported.append(metrics_data)
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: object) -> None:
        return None


def job_telemetry() -> tuple[Telemetry, InMemorySpanExporter, RecordingMetricExporter]:
    spans = InMemorySpanExporter()
    metrics = RecordingMetricExporter()
    telemetry = setup_telemetry(
        span_exporter=spans,
        metric_readers=[PeriodicExportingMetricReader(metrics, export_interval_millis=3_600_000)],
        environ={},
    )
    return telemetry, spans, metrics


class FakeQualityStore:
    def __init__(self) -> None:
        self.is_database_reachable = True
        self.checked: list[CheckedDay] = [
            CheckedDay(FROM, Status.WARN, "run-1", AS_OF),
        ]
        self.stored_findings: list[Finding] = [
            Finding(
                Rule.MISSING_DATE,
                Severity.WARN,
                FROM,
                None,
                None,
                None,
                "No value was published for this TARGET business day.",
                "No value for any maturity on 2026-10-07",
            )
        ]
        self.maturity_filter: str | None = None

    async def is_ready(self) -> bool:
        return self.is_database_reachable

    async def current_time(self) -> datetime:
        return AS_OF

    async def checked_days(
        self, curve_id: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[CheckedDay]:
        return self.checked

    async def findings(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[Finding]:
        return self.stored_findings

    async def value_statuses(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[ValueStatus]:
        self.maturity_filter = maturity
        return [ValueStatus(1, "10Y", FROM, Status.WARN)]


@dataclass
class StubCheckRunHistory:
    """Answers from ``attempts`` (given newest first) and records the keyword arguments."""

    attempts: list[CheckRunAttempt] = field(default_factory=list)
    list_calls: list[dict[str, object]] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)

    async def list_check_runs(
        self,
        *,
        recorded_from: datetime | None,
        recorded_before: datetime | None,
        before_check_run_id: int | None,
        limit: int,
    ) -> Sequence[CheckRunAttempt]:
        self.list_calls.append(
            {
                "recorded_from": recorded_from,
                "recorded_before": recorded_before,
                "before_check_run_id": before_check_run_id,
                "limit": limit,
            }
        )
        rows = [
            attempt
            for attempt in self.attempts
            if before_check_run_id is None or attempt.check_run_id < before_check_run_id
        ]
        return rows[:limit]

    async def get_check_runs(self, run_id: str) -> Sequence[CheckRunAttempt]:
        self.get_calls.append(run_id)
        return sorted(
            (attempt for attempt in self.attempts if attempt.run_id == run_id),
            key=lambda attempt: attempt.attempt,
        )
