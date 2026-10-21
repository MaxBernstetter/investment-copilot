"""Telemetry for the job tests: spans and metrics are kept in memory, nothing is sent."""

from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ingestion.infrastructure.telemetry import Telemetry, setup_telemetry


class RecordingMetricExporter(MetricExporter):
    """Keeps every exported batch of metrics; the job's reader exports only at shutdown here."""

    def __init__(self) -> None:
        super().__init__()
        self.exported: list[MetricsData] = []
        self.is_shut_down = False

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs: object
    ) -> MetricExportResult:
        self.exported.append(metrics_data)
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: object) -> None:
        self.is_shut_down = True


def job_telemetry() -> tuple[Telemetry, InMemorySpanExporter, RecordingMetricExporter]:
    spans = InMemorySpanExporter()
    metrics = RecordingMetricExporter()
    telemetry = setup_telemetry(
        span_exporter=spans,
        metric_readers=[PeriodicExportingMetricReader(metrics, export_interval_millis=3_600_000)],
        environ={},
    )
    return telemetry, spans, metrics
