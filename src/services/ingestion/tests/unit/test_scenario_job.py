"""The scenario job end to end inside ingestion: a scenario in, contract requests to a
persistence stub out. No live source and no network are used; the pause is a no-op."""

import json
from dataclasses import dataclass

import pytest
from opentelemetry.trace import StatusCode, format_span_id, format_trace_id

from ingestion.infrastructure.telemetry import Telemetry
from ingestion.job import run_scenario
from tests.fake_telemetry import job_telemetry
from tests.stub_persistence import KNOWN_FROM, URL, StubPersistence


@dataclass
class Run:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def summary(self) -> dict[str, object]:
        result: dict[str, object] = json.loads(self.stdout)
        return result


async def _no_pause(seconds: float) -> None:
    """Replaces the real pause between two events."""


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", URL)
    # Required at startup by the shared settings; the scenario job does not use ING.
    monkeypatch.setenv("INGESTION_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "not-a-secret")


def run(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    persistence: StubPersistence,
    telemetry: Telemetry | None = None,
) -> Run:
    exit_code = run_scenario(
        argv,
        persistence_transport=persistence.transport,
        sleep=_no_pause,
        telemetry=telemetry,
    )
    captured = capsys.readouterr()
    return Run(exit_code, captured.out, captured.err)


def test_runs_the_scenario_and_prints_one_summary_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    persistence = StubPersistence()

    result = run(capsys, ["corrected-yield"], persistence)

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    summary = result.summary
    assert summary["event"] == "scenario_finished"
    assert summary["scenario"] == "corrected-yield"
    assert summary["curve_id"] == "ecb-aaa-spot-sim"
    events = summary["events"]
    assert isinstance(events, list)
    assert [event["name"] for event in events] == [
        "publish",
        "gap",
        "bad-value",
        "late-value",
        "correction",
    ]
    assert all(event["known_from"] == KNOWN_FROM.isoformat() for event in events)
    assert [event["run_id"] for event in events] == [
        f"scenario-corrected-yield-{name}"
        for name in ("publish", "gap", "bad-value", "late-value", "correction")
    ]
    assert len(persistence.batches) == 5


def test_runs_a_single_event(capsys: pytest.CaptureFixture[str]) -> None:
    persistence = StubPersistence()

    result = run(capsys, ["corrected-yield", "--event", "correction"], persistence)

    assert result.exit_code == 0
    events = result.summary["events"]
    assert isinstance(events, list)
    assert [event["name"] for event in events] == ["correction"]
    [batch] = persistence.batches
    assert {o.curve_id for o in batch.observations} == {"ecb-aaa-spot-sim"}


def test_unknown_scenario_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    persistence = StubPersistence()

    with pytest.raises(SystemExit) as exit_info:
        run(capsys, ["no-such-scenario"], persistence)

    assert exit_info.value.code == 2
    assert persistence.attempts == 0


def test_unknown_event_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    persistence = StubPersistence()

    with pytest.raises(SystemExit) as exit_info:
        run(capsys, ["corrected-yield", "--event", "no-such-event"], persistence)

    assert exit_info.value.code == 2
    assert persistence.attempts == 0


def test_rejected_write_fails_with_status_1(capsys: pytest.CaptureFixture[str]) -> None:
    persistence = StubPersistence(statuses=[422])

    result = run(capsys, ["corrected-yield"], persistence)

    assert result.exit_code == 1
    assert result.stdout == ""
    failure = json.loads(result.stderr)
    assert failure["event"] == "scenario_failed"
    assert failure["scenario"] == "corrected-yield"
    assert failure["error"]


def test_a_scenario_run_has_one_root_span_and_trace_ids_in_its_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, spans, metrics = job_telemetry()

    result = run(capsys, ["corrected-yield"], StubPersistence(), telemetry)

    assert result.exit_code == 0
    [span] = spans.get_finished_spans()
    assert span.name == "ingestion-scenario"
    assert span.parent is None
    assert dict(span.attributes or {}) == {"scenario": "corrected-yield"}
    assert result.summary["trace_id"] == format_trace_id(span.context.trace_id)
    assert result.summary["span_id"] == format_span_id(span.context.span_id)
    assert metrics.is_shut_down


def test_a_failed_scenario_flushes_and_carries_trace_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    telemetry, spans, metrics = job_telemetry()

    result = run(capsys, ["corrected-yield"], StubPersistence(statuses=[422]), telemetry)

    assert result.exit_code == 1
    [span] = spans.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    failure = json.loads(result.stderr)
    assert failure["trace_id"] == format_trace_id(span.context.trace_id)
    assert failure["span_id"] == format_span_id(span.context.span_id)
    assert metrics.is_shut_down
