import json
import logging
import logging.config
import os
from io import StringIO
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import format_span_id, format_trace_id

from ingestion.infrastructure.telemetry import metrics_configured, traces_configured
from ingestion.job import main
from tests.fake_deliveries import FakeDeliveryStore
from tests.fake_run_log import FakeRunLog
from tests.recorded import DAILY
from tests.stub_persistence import URL, StubPersistence
from tests.unit.test_load_ecb_job import StubEcb

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
def test_traces_and_metrics_are_configured_per_signal(
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
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", URL)
    monkeypatch.setenv("INGESTION_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "not-a-secret")
    monkeypatch.setenv("INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS", "0")
    caplog.set_level(logging.WARNING)
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})

    exit_code = main(
        ["daily", "--valid-date", "2026-10-15"],
        source_transport=ecb.transport,
        persistence_transport=StubPersistence().transport,
        delivery_store=FakeDeliveryStore(),
        run_log=FakeRunLog(),
    )

    assert exit_code == 0
    assert not [record for record in caplog.records if record.name.startswith("opentelemetry")]


def test_log_lines_carry_trace_and_span_id_inside_a_span(monkeypatch: pytest.MonkeyPatch) -> None:
    logging.config.dictConfig(json.loads(LOG_CONFIG.read_text(encoding="utf-8")))
    handler = logging.getHandlerByName("stderr")
    assert isinstance(handler, logging.StreamHandler)
    stream = StringIO()
    monkeypatch.setattr(handler, "stream", stream)
    logger = logging.getLogger("ingestion.test")
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
