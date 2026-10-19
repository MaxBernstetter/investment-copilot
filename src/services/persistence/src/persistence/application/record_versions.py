"""Use case: record a batch of observations as versions (one transaction, never overwriting)."""

from collections.abc import Sequence
from typing import Protocol

from persistence.domain.observation import Observation, RecordedVersions, ensure_unique_keys


class ObservationRepository(Protocol):
    """Port to the bitemporal store."""

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        """Record every observation in one transaction, all or nothing.

        A new or changed observation (value or source) becomes the open version;
        a changed one closes the previous open version. An unchanged one is a no-op.
        Raises OpenVersionExistsError if a concurrent write got in first.
        """
        ...


class RecordVersions:
    def __init__(self, repository: ObservationRepository) -> None:
        self._repository = repository

    async def __call__(self, observations: Sequence[Observation]) -> RecordedVersions:
        ensure_unique_keys(observations)
        return await self._repository.record_versions(observations)
