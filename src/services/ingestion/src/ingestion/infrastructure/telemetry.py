"""OpenTelemetry setup of the ingestion service: providers, exporters and trace ids in logs.

The providers are built here and passed explicitly; the global tracer and meter providers are
never set. Exporters are attached only when an OTLP endpoint is configured through the standard
``OTEL_EXPORTER_OTLP_*`` variables, so the job and the tests run without a collector.
"""

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span, Tracer

from ingestion.application.track_run import RunLog
from ingestion.domain.run import Operation, RunOutcome

TRACES_ENDPOINT_VARIABLES = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
METRICS_ENDPOINT_VARIABLES = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")


def traces_configured(environ: Mapping[str, str]) -> bool:
    """True when a trace endpoint variable is set to a non-empty value."""
    return any(environ.get(name) for name in TRACES_ENDPOINT_VARIABLES)


def metrics_configured(environ: Mapping[str, str]) -> bool:
    """True when a metric endpoint variable is set to a non-empty value."""
    return any(environ.get(name) for name in METRICS_ENDPOINT_VARIABLES)


@dataclass(frozen=True, slots=True)
class Telemetry:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    @property
    def tracer(self) -> Tracer:
        return self.tracer_provider.get_tracer("ingestion")

    @property
    def meter(self) -> Meter:
        return self.meter_provider.get_meter("ingestion")

    def shutdown(self) -> None:
        """Flush and stop the tracer, then the meter."""
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


def setup_telemetry(
    *,
    span_exporter: SpanExporter | None = None,
    metric_readers: Sequence[MetricReader] = (),
    environ: Mapping[str, str] = os.environ,
) -> Telemetry:
    resource = Resource.create()
    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    elif traces_configured(environ):
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    readers: list[MetricReader] = list(metric_readers)
    if not readers and metrics_configured(environ):
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    return Telemetry(tracer_provider, meter_provider)


def trace_fields() -> dict[str, str]:
    """Trace and span ids of the current span as lowercase hex; empty outside a valid span."""
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {
        "trace_id": trace.format_trace_id(context.trace_id),
        "span_id": trace.format_span_id(context.span_id),
    }


class TraceContextFilter(logging.Filter):
    """Adds ``trace_id`` and ``span_id`` to records emitted inside a valid span."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in trace_fields().items():
            setattr(record, name, value)
        return True


class AttemptOnSpan:
    """A run log that sets the attempt number of each started run on the given span.

    The attempt is known only once the run log has started the run, so the job wraps its run
    log in this class and the root span of the job receives ``attempt``.
    """

    def __init__(self, run_log: RunLog, span: Span) -> None:
        self._run_log = run_log
        self._span = span

    async def start(self, run_id: str, operation: Operation) -> int:
        attempt = await self._run_log.start(run_id, operation)
        self._span.set_attribute("attempt", attempt)
        return attempt

    async def finish(self, run_id: str, attempt: int, outcome: RunOutcome) -> None:
        await self._run_log.finish(run_id, attempt, outcome)

    async def fail_unfinished(self, run_id: str, error_type: str, error_message: str | None) -> int:
        return await self._run_log.fail_unfinished(run_id, error_type, error_message)
