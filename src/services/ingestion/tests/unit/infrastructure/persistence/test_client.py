"""PersistenceClient against a stub of the write interface. No network."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import pytest
from contracts.persistence import v1

from ingestion.application.load_published_curve import RecordedBatch
from ingestion.application.run_scenario import RunScenario
from ingestion.config import PersistenceSettings
from ingestion.domain.observation import PublishedObservation
from ingestion.domain.scenario import SCENARIO_SOURCE_ID
from ingestion.domain.scenarios import CORRECTED_YIELD, SIMULATED_CURVE_ID
from ingestion.infrastructure.persistence import PersistenceClient, PersistenceWriteError
from tests.stub_persistence import KNOWN_FROM, URL, StubPersistence

pytestmark = pytest.mark.anyio

SETTINGS = PersistenceSettings.model_validate({"url": URL})


def observations(count: int) -> list[PublishedObservation]:
    return [
        PublishedObservation(
            "ecb-aaa-spot", "10Y", date(2000, 1, 1) + timedelta(days=i), Decimal(i), "1"
        )
        for i in range(count)
    ]


@dataclass
class FakeSleep:
    waits: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


async def record(
    stub: StubPersistence, rows: list[PublishedObservation], sleep: FakeSleep | None = None
) -> list[RecordedBatch]:
    async with PersistenceClient(
        SETTINGS, transport=stub.transport, sleep=sleep or FakeSleep()
    ) as client:
        return await client.record("ecb", rows, "run-1", "delivery-7")


async def test_observations_are_sent_as_published_versions_of_the_run_and_delivery() -> None:
    stub = StubPersistence()

    result = await record(stub, observations(1))

    assert result == [RecordedBatch(1, 0, KNOWN_FROM)]
    assert stub.observations == [
        v1.ObservationVersion(
            curve_id="ecb-aaa-spot",
            maturity="10Y",
            valid_date=date(2000, 1, 1),
            value=Decimal(0),
            origin=v1.Origin.PUBLISHED,
            method_version=None,
            source_id="ecb",
            run_id="run-1",
            change_reason=v1.ChangeReason.INITIAL,
            normalization_version="1",
            delivery_id="delivery-7",
        )
    ]


async def test_large_loads_are_split_into_batches_of_the_contract_maximum() -> None:
    stub = StubPersistence()

    result = await record(stub, observations(v1.MAX_BATCH_SIZE + 1))

    assert [len(batch.observations) for batch in stub.batches] == [v1.MAX_BATCH_SIZE, 1]
    assert [batch.recorded_count for batch in result] == [v1.MAX_BATCH_SIZE, 1]


async def test_unchanged_values_are_reported_as_no_ops() -> None:
    # Versioning (#15): an unchanged reload stores nothing and is still a success.
    stub = StubPersistence(unchanged_count=3)

    assert await record(stub, observations(3)) == [RecordedBatch(0, 3, KNOWN_FROM)]


async def test_a_response_without_unchanged_count_means_none_unchanged() -> None:
    # Persistence before versioning (#12) has no unchanged_count.
    stub = StubPersistence(include_unchanged_count=False)

    assert await record(stub, observations(3)) == [RecordedBatch(3, 0, KNOWN_FROM)]


async def test_a_concurrent_write_conflict_is_retried_with_backoff() -> None:
    stub = StubPersistence(statuses=[409, 409])
    sleep = FakeSleep()

    result = await record(stub, observations(2), sleep)

    assert result == [RecordedBatch(2, 0, KNOWN_FROM)]
    assert stub.attempts == 3
    assert sleep.waits == [0.5, 1.0]


async def test_conflicts_are_retried_at_most_three_times_in_all() -> None:
    stub = StubPersistence(statuses=[409, 409, 409, 200])

    with pytest.raises(PersistenceWriteError) as raised:
        await record(stub, observations(1))

    assert raised.value.status_code == 409
    assert stub.attempts == 3


@pytest.mark.parametrize("status_code", [422, 500, 503])
async def test_other_rejections_fail_the_write_without_retry(status_code: int) -> None:
    stub = StubPersistence(statuses=[status_code])

    with pytest.raises(PersistenceWriteError) as raised:
        await record(stub, observations(1))

    assert raised.value.status_code == status_code
    assert stub.attempts == 1


async def test_records_a_scenario_event_as_published_scenario_values() -> None:
    stub = StubPersistence()
    event = CORRECTED_YIELD.event("correction")

    async with PersistenceClient(SETTINGS, transport=stub.transport, sleep=FakeSleep()) as client:
        result = await client.record_event(SIMULATED_CURVE_ID, event, "scenario-run-1")

    assert result == RecordedBatch(1, 0, KNOWN_FROM)
    assert stub.observations == [
        v1.ObservationVersion(
            curve_id=SIMULATED_CURVE_ID,
            maturity="10Y",
            valid_date=date(2026, 10, 8),
            value=Decimal("2.64"),
            origin=v1.Origin.PUBLISHED,
            source_id=SCENARIO_SOURCE_ID,
            run_id="scenario-run-1",
            change_reason=v1.ChangeReason.CORRECTION,
        )
    ]


async def test_every_scenario_write_targets_only_the_simulated_curve() -> None:
    stub = StubPersistence()
    sleep = FakeSleep()

    async with PersistenceClient(SETTINGS, transport=stub.transport, sleep=sleep) as client:
        result = await RunScenario(client, sleep)(CORRECTED_YIELD)

    assert len(result.events) == 5
    assert stub.observations
    assert {observation.curve_id for observation in stub.observations} == {SIMULATED_CURVE_ID}
    assert {observation.source_id for observation in stub.observations} == {SCENARIO_SOURCE_ID}
