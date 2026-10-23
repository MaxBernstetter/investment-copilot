"""The load command line for any source: pure facade, no I/O."""

import json

import pytest

from ingestion.application.load_published_curve import LoadResult
from ingestion.application.replay_deliveries import ReplayResult
from ingestion.domain.run import Operation
from ingestion.facade.jobs.load import (
    FailUnfinishedCommand,
    LoadCommand,
    ReplayCommand,
    failure,
    job_name,
    parse_command,
    replay_summary,
    root_span_attributes,
    summary,
    unfinished_summary,
)

ECB_DESCRIPTION = (
    "Load the ECB euro area spot curves (AAA and all issuers) into the bitemporal core."
)
LOOKBACK = 10
TRACE = {"trace_id": "t", "span_id": "s"}


def parse(
    argv: list[str], source_id: str = "ecb"
) -> LoadCommand | ReplayCommand | FailUnfinishedCommand:
    return parse_command(
        argv,
        source_id=source_id,
        description=ECB_DESCRIPTION,
        lookback_business_days=LOOKBACK,
    )


def test_job_name_is_derived_from_the_source() -> None:
    assert job_name("ecb") == "ingestion-load-ecb"
    assert job_name("ust") == "ingestion-load-ust"


@pytest.mark.parametrize(
    ("argv", "run_id"),
    [
        (["daily", "--valid-date", "2026-10-15"], "ecb-daily-2026-10-15"),
        (
            ["history", "--start", "2004-09-06", "--end", "2026-10-16"],
            "ecb-history-2004-09-06-2026-10-16",
        ),
        (
            ["replay", "--fetched-from", "2026-10-01", "--fetched-to", "2026-10-18"],
            "ecb-replay-2026-10-01-2026-10-18",
        ),
        (["daily", "--valid-date", "2026-10-15", "--run-id", "X"], "X"),
    ],
)
def test_ecb_run_ids_are_unchanged(argv: list[str], run_id: str) -> None:
    command = parse(argv)

    assert not isinstance(command, FailUnfinishedCommand)
    assert command.run_id == run_id


@pytest.mark.parametrize(
    ("argv", "run_id"),
    [
        (["daily", "--valid-date", "2026-10-15"], "ust-daily-2026-10-15"),
        (
            ["history", "--start", "2004-09-06", "--end", "2026-10-16"],
            "ust-history-2004-09-06-2026-10-16",
        ),
        (
            ["replay", "--fetched-from", "2026-10-01", "--fetched-to", "2026-10-18"],
            "ust-replay-2026-10-01-2026-10-18",
        ),
    ],
)
def test_run_ids_carry_the_source_id(argv: list[str], run_id: str) -> None:
    command = parse(argv, source_id="ust")

    assert not isinstance(command, FailUnfinishedCommand)
    assert command.run_id == run_id


def test_parser_prog_is_the_job_name(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse(["--help"])

    assert capsys.readouterr().out.startswith("usage: ingestion-load-ecb")


def test_summaries_name_the_source() -> None:
    load = LoadResult("ust-daily-2026-10-15", 1, ())
    replay = ReplayResult("ust-replay-2026-10-01-2026-10-18", 1, ())

    outputs = [
        json.loads(summary("ust", load, TRACE)),
        json.loads(replay_summary("ust", replay, TRACE)),
        json.loads(unfinished_summary("ust", "ust-daily-2026-10-15", 2, TRACE)),
        json.loads(failure("ust", "ust-daily-2026-10-15", ValueError("x"), TRACE)),
    ]

    assert [output["source"] for output in outputs] == ["ust"] * 4


def test_ecb_summary_keys_keep_their_order() -> None:
    result = LoadResult("ecb-daily-2026-10-15", 1, ())

    output = json.loads(summary("ecb", result, TRACE))

    assert list(output)[:4] == ["event", "source", "run_id", "attempt"]
    assert output["source"] == "ecb"
    assert output["event"] == "load_finished"


def test_root_span_attributes_name_the_source() -> None:
    command = parse(["daily", "--valid-date", "2026-10-15"], source_id="ust")

    attributes = root_span_attributes(command, "ust")

    assert attributes == {
        "run_id": "ust-daily-2026-10-15",
        "source": "ust",
        "operation": Operation.DAILY.value,
    }


def test_fail_unfinished_command_has_no_default_run_id() -> None:
    command = parse(["fail-unfinished", "--run-id", "ecb-daily-2026-10-15", "--error-type", "E"])

    assert command == FailUnfinishedCommand("ecb-daily-2026-10-15", "E", None)
