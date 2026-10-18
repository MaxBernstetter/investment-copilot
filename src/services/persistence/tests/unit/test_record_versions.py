import pytest

from persistence.application.record_versions import RecordVersions
from persistence.domain.observation import InvalidObservationsError, RecordedVersions
from tests.unit.fakes import KNOWN_FROM, InMemoryObservationRepository, published

pytestmark = pytest.mark.anyio


async def test_records_every_observation_with_one_knowledge_time() -> None:
    repository = InMemoryObservationRepository()
    batch = [published(maturity="2Y"), published(maturity="10Y")]

    recorded = await RecordVersions(repository)(batch)

    assert recorded == RecordedVersions(known_from=KNOWN_FROM, recorded_count=2, unchanged_count=0)
    assert repository.versions == [(batch[0], KNOWN_FROM), (batch[1], KNOWN_FROM)]


async def test_rejects_a_batch_with_duplicates_before_storing_anything() -> None:
    repository = InMemoryObservationRepository()

    with pytest.raises(InvalidObservationsError):
        await RecordVersions(repository)([published(), published()])

    assert repository.versions == []
