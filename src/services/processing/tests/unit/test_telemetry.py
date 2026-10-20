import json
import logging
import logging.config
import os
from io import StringIO
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import format_span_id, format_trace_id

from processing.infrastructure.telemetry import metrics_configured, traces_configured
from processing.job import main
from tests.unit.test_check_quality_job import (
    CURVE_ID,
    FROM,
    TO,
    RecordingStore,
    _curve_after_bad_value,
    _transport,
)

LOG_CONFIG = Path(__file__).parents[2] / "log_config.json"


@pytest.mark.parametrize(
    ("environ", "traces", "metrics"),
    [
        ({}, False, False),
        ({"OTEL_SERVICE_NAME": "x"}, False, False),
        ({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://x:4318"}, True, True),
        ({"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://x:4318/v1/traces"}, True, False),
        ({"OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "http://x:4318/v1/metrics"}, False, True),
        (
            {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": ""},
            False,
            False,
        ),
    ],
)
def test_each_signal_exports_only_with_its_own_endpoint(
    environ: dict[str, str], traces: bool, metrics: bool
) -> None:
    assert traces_configured(environ) is traces
    assert metrics_configured(environ) is metrics


def test_without_otel_env_the_job_runs_and_logs_no_exporter_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name in list(os.environ):
        if name.startswith("OTEL_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence.test:8001")
    monkeypatch.setenv("PROCESSING_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("PROCESSING_DB__PASSWORD", "not-a-secret")
    caplog.set_level(logging.WARNING)

    exit_code = main(
        [CURVE_ID, "--from", FROM.isoformat(), "--to", TO.isoformat()],
        persistence_transport=_transport(_curve_after_bad_value()),
        quality_store=RecordingStore(),
    )

    assert exit_code == 0
    assert not [record for record in caplog.records if record.name.startswith("opentelemetry")]


def test_log_lines_carry_trace_and_span_id_inside_a_span(monkeypatch: pytest.MonkeyPatch) -> None:
    logging.config.dictConfig(json.loads(LOG_CONFIG.read_text(encoding="utf-8")))
    handler = logging.getHandlerByName("stderr")
    assert isinstance(handler, logging.StreamHandler)
    stream = StringIO()
    monkeypatch.setattr(handler, "stream", stream)
    logger = logging.getLogger("processing.test")
    tracer = TracerProvider().get_tracer("test")

    with tracer.start_as_current_span("work") as span:
        logger.info("inside")
        context = span.get_span_context()
    logger.info("outside")

    inside, outside = (json.loads(line) for line in stream.getvalue().strip().splitlines()[-2:])
    assert inside["trace_id"] == format_trace_id(context.trace_id)
    assert inside["span_id"] == format_span_id(context.span_id)
    assert "trace_id" not in outside
    assert "span_id" not in outside
