"""Test doubles and fixtures shared by the unit tests."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from persistence.domain.observation import (
    ChangeReason,
    Observation,
    ObservationKey,
    OpenVersionExistsError,
    Origin,
    RecordedVersions,
)

KNOWN_FROM = datetime(2026, 3, 12, 18, 0, tzinfo=UTC)


def published(maturity: str = "10Y", value: str = "2.61", **changes: object) -> Observation:
    observation = Observation(
        curve_id="ecb-aaa-spot",
        maturity=maturity,
        valid_date=date(2026, 3, 12),
        value=Decimal(value),
        origin=Origin.PUBLISHED,
        method_version=None,
        source_id="ecb",
        run_id="ingestion-ecb-2026-03-12",
        change_reason=ChangeReason.INITIAL,
    )
    return replace(observation, **changes)  # type: ignore[arg-type]


class InMemoryObservationRepository:
    """Records versions in memory with a fixed knowledge time."""

    def __init__(self) -> None:
        self.versions: list[tuple[Observation, datetime]] = []

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        open_keys: set[ObservationKey] = {stored.key for stored, _ in self.versions}
        if any(observation.key in open_keys for observation in observations):
            raise OpenVersionExistsError("open version exists")
        self.versions.extend((observation, KNOWN_FROM) for observation in observations)
        return RecordedVersions(known_from=KNOWN_FROM, recorded_count=len(observations))
