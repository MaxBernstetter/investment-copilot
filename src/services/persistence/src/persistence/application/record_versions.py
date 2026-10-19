"""Use case: record a batch of observations as new versions (one transaction)."""

from collections.abc import Sequence
from typing import Protocol

from persistence.domain.observation import Observation, RecordedVersions, ensure_unique_keys


class ObservationRepository(Protocol):
    """Port to the bitemporal store."""

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        """Store every observation as a new open version in one transaction.

        Raises OpenVersionExistsError if one of them already has an open version.
        """
        ...


class RecordVersions:
    def __init__(self, repository: ObservationRepository) -> None:
        self._repository = repository

    async def __call__(self, observations: Sequence[Observation]) -> RecordedVersions:
        ensure_unique_keys(observations)
        return await self._repository.record_versions(observations)
