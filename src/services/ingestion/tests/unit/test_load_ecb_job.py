"""The ECB load job end to end inside ingestion: recorded ECB payloads in, contract
requests to a persistence stub out. No live source and no network are used."""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from contracts.persistence import v1

from ingestion.infrastructure.http import USER_AGENT
from ingestion.job import main
from tests.fake_deliveries import FakeDeliveryStore
from tests.recorded import (
    DAILY,
    EMPTY_WINDOW,
    HISTORY_2025,
    HISTORY_2026,
    MALFORMED,
    NO_SERIES_404,
    payload,
    recorded_response,
)
from tests.stub_persistence import KNOWN_FROM, URL, StubPersistence

ECB_DATA_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM."
    "SR_3M+SR_6M+SR_1Y+SR_2Y+SR_3Y+SR_5Y+SR_7Y+SR_10Y+SR_15Y+SR_20Y+SR_30Y"
)
GRID = {"3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"}


@dataclass
class StubEcb:
    """Answers each requested window with the recorded payload for it."""

    payloads: dict[tuple[str, str], str]
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        window = (request.url.params["startPeriod"], request.url.params["endPeriod"])
        return recorded_response(self.payloads[window])

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


@dataclass
class Run:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.stdout)
        return result


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", URL)
    # Required at startup; the tests inject an in-memory delivery store instead.
    monkeypatch.setenv("INGESTION_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "not-a-secret")
    # Pacing is the source client's concern (tested there); here it would only slow tests.
    monkeypatch.setenv("INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS", "0")


def run(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    ecb: StubEcb,
    persistence: StubPersistence,
    deliveries: FakeDeliveryStore | None = None,
) -> Run:
    exit_code = main(
        argv,
        source_transport=ecb.transport,
        persistence_transport=persistence.transport,
        delivery_store=deliveries or FakeDeliveryStore(),
    )
    captured = capsys.readouterr()
    return Run(exit_code, captured.out, captured.err)


def test_daily_load_requests_the_whole_grid_in_one_polite_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})

    run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, StubPersistence())

    [request] = ecb.requests
    assert str(request.url.copy_with(query=None)) == ECB_DATA_URL
    assert dict(request.url.params) == {
        "startPeriod": "2026-10-01",
        "endPeriod": "2026-10-15",
        "format": "csvdata",
        "detail": "dataonly",
    }
    assert request.headers["User-Agent"] == USER_AGENT


def test_daily_load_stores_all_11_tenors_as_published_values_of_the_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence)

    assert result.exit_code == 0
    stored = persistence.observations
    assert {o.maturity for o in stored if o.valid_date == date(2026, 10, 15)} == GRID
    assert Counter(o.valid_date for o in stored) == {
        day: 11 for day in (date(2026, 10, d) for d in (1, 2, 5, 6, 7, 8, 9, 12, 13, 14, 15))
    }
    assert {(o.curve_id, o.origin, o.method_version, o.source_id, o.run_id) for o in stored} == {
        ("ecb-aaa-spot", v1.Origin.PUBLISHED, None, "ecb", "ecb-daily-2026-10-15")
    }
    assert result.summary["recorded_count"] == 121


def test_the_answer_is_kept_byte_for_byte_and_every_value_names_its_delivery(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})
    deliveries = FakeDeliveryStore()
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence, deliveries)

    [(delivery, run_id)] = deliveries.stored
    assert run_id == "ecb-daily-2026-10-15"
    assert delivery.payload == payload(DAILY)
    assert delivery.source_id == "ecb"
    assert delivery.request_url == str(ecb.requests[0].url)
    assert delivery.response_status == 200
    assert delivery.last_modified == datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
    assert delivery.etag is None
    assert delivery.fetched_at.tzinfo is not None
    assert {o.delivery_id for o in persistence.observations} == {"1"}
    assert result.summary["windows"][0]["delivery_id"] == "1"


def test_published_values_are_stored_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})
    persistence = StubPersistence()

    run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence)

    ten_year = {o.valid_date: o.value for o in persistence.observations if o.maturity == "10Y"}
    assert ten_year[date(2026, 10, 1)] == Decimal("3.5921733451")


def test_lookback_and_run_id_are_configurable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS", "4")
    ecb = StubEcb({("2026-10-09", "2026-10-15"): EMPTY_WINDOW})

    result = run(
        capsys,
        ["daily", "--valid-date", "2026-10-15", "--run-id", "dag-run-7"],
        ecb,
        StubPersistence(),
    )

    assert [dict(r.url.params)["startPeriod"] for r in ecb.requests] == ["2026-10-09"]
    assert result.summary["run_id"] == "dag-run-7"


def test_knowledge_time_is_set_by_persistence_and_last_modified_is_delivery_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence)

    # The write carries no time of the source: the contract has no knowledge-time field,
    # so persistence's database clock sets known_from.
    sent = json.loads(persistence.batches[0].model_dump_json())["observations"][0]
    assert "known_from" not in sent
    assert "last_modified" not in sent
    [window] = result.summary["windows"]
    assert window["known_from"] == [KNOWN_FROM.isoformat()]
    assert window["last_modified"] == "2026-10-16T10:00:00+00:00"


@pytest.mark.parametrize(
    "fixture",
    [
        pytest.param(NO_SERIES_404, id="ECB 404 no data"),
        pytest.param(EMPTY_WINDOW, id="200 with empty body"),
    ],
)
def test_an_empty_window_is_a_successful_run_with_zero_rows_and_no_retry(
    capsys: pytest.CaptureFixture[str], fixture: str
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): fixture})
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence)

    assert result.exit_code == 0
    assert len(ecb.requests) == 1
    assert persistence.batches == []
    assert result.summary["delivered_count"] == 0
    assert result.summary["recorded_count"] == 0


@pytest.mark.parametrize(
    ("fixture", "status"),
    [
        pytest.param(NO_SERIES_404, 404, id="ECB 404 no data"),
        pytest.param(EMPTY_WINDOW, 200, id="200 with empty body"),
    ],
)
def test_an_empty_window_is_kept_as_a_delivery_without_payload(
    capsys: pytest.CaptureFixture[str], fixture: str, status: int
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): fixture})
    deliveries = FakeDeliveryStore()

    result = run(
        capsys, ["daily", "--valid-date", "2026-10-15"], ecb, StubPersistence(), deliveries
    )

    [delivery] = deliveries.deliveries
    assert (delivery.response_status, delivery.payload) == (status, None)
    assert result.summary["windows"][0]["delivery_id"] == "1"


def test_history_loads_one_calendar_year_per_request_in_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb(
        {("2025-12-22", "2025-12-31"): HISTORY_2025, ("2026-01-01", "2026-01-09"): HISTORY_2026}
    )
    persistence = StubPersistence()

    result = run(
        capsys, ["history", "--start", "2025-12-22", "--end", "2026-01-09"], ecb, persistence
    )

    assert result.exit_code == 0
    assert [(r.url.params["startPeriod"], r.url.params["endPeriod"]) for r in ecb.requests] == [
        ("2025-12-22", "2025-12-31"),
        ("2026-01-01", "2026-01-09"),
    ]
    assert [len(batch.observations) for batch in persistence.batches] == [66, 66]
    assert [{o.delivery_id for o in batch.observations} for batch in persistence.batches] == [
        {"1"},
        {"2"},
    ]
    assert {o.run_id for o in persistence.observations} == {"ecb-history-2025-12-22-2026-01-09"}
    assert result.summary["recorded_count"] == 132


def test_a_malformed_payload_fails_the_run_and_writes_nothing_but_the_delivery(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): MALFORMED})
    deliveries = FakeDeliveryStore()
    persistence = StubPersistence()

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence, deliveries)

    assert result.exit_code == 1
    assert persistence.batches == []
    assert [d.payload for d in deliveries.deliveries] == [payload(MALFORMED)]
    failure = json.loads(result.stderr)
    assert failure["event"] == "load_failed"
    assert failure["error"] == "InvalidPayloadError"
    assert failure["run_id"] == "ecb-daily-2026-10-15"


def test_a_rejected_write_fails_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})

    result = run(
        capsys, ["daily", "--valid-date", "2026-10-15"], ecb, StubPersistence(statuses=[422])
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"] == "PersistenceWriteError"


def test_a_lookback_rerun_over_stored_values_reports_them_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Against persistence with versioning (#15, PR #71): unchanged values are no-ops.
    ecb = StubEcb({("2026-10-01", "2026-10-15"): DAILY})
    persistence = StubPersistence(unchanged_count=121)

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, persistence)

    assert result.exit_code == 0
    assert (result.summary["recorded_count"], result.summary["unchanged_count"]) == (0, 121)


def test_the_kill_switch_stops_the_run_before_any_request(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INGESTION_SOURCES__ECB__ENABLED", "false")
    ecb = StubEcb({})

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], ecb, StubPersistence())

    assert result.exit_code == 1
    assert ecb.requests == []
    assert json.loads(result.stderr)["error"] == "SourceDisabledError"


def test_missing_configuration_is_a_startup_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("INGESTION_PERSISTENCE__URL")

    result = run(capsys, ["daily", "--valid-date", "2026-10-15"], StubEcb({}), StubPersistence())

    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"] == "ValidationError"


@pytest.mark.parametrize(
    "argv",
    [
        ["daily"],
        ["daily", "--valid-date", "15.10.2026"],
        ["history", "--start", "2026-01-02", "--end", "2026-01-01"],
        ["weekly", "--valid-date", "2026-10-15"],
    ],
)
def test_invalid_arguments_are_usage_errors(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(argv)

    assert raised.value.code == 2
