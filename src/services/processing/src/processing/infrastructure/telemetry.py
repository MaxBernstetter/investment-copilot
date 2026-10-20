"""OpenTelemetry setup of the processing service: providers, exporters and trace ids in logs.

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
from opentelemetry.trace import Tracer

OTLP_ENDPOINT_VARIABLES = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
)


def otlp_configured(environ: Mapping[str, str]) -> bool:
    """True when any OTLP endpoint variable is set to a non-empty value."""
    return any(environ.get(name) for name in OTLP_ENDPOINT_VARIABLES)


@dataclass(frozen=True, slots=True)
class Telemetry:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    @property
    def tracer(self) -> Tracer:
        return self.tracer_provider.get_tracer("processing")

    @property
    def meter(self) -> Meter:
        return self.meter_provider.get_meter("processing")

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
    configured = otlp_configured(environ)
    resource = Resource.create()
    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    elif configured:
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    readers: list[MetricReader] = list(metric_readers)
    if not readers and configured:
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
