"""Test doubles and fixtures shared by the unit tests."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from persistence.domain.observation import (
    ChangeReason,
    Observation,
    ObservationKey,
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
    """Records versions in memory like core_observation, at a settable knowledge time."""

    def __init__(self) -> None:
        self.known_from = KNOWN_FROM
        self.versions: list[tuple[Observation, datetime]] = []
        self.open_versions: dict[ObservationKey, Observation] = {}

    async def record_versions(self, observations: Sequence[Observation]) -> RecordedVersions:
        changed = [o for o in observations if not self._is_unchanged(o)]
        for observation in changed:
            self.open_versions[observation.key] = observation
            self.versions.append((observation, self.known_from))
        return RecordedVersions(
            known_from=self.known_from,
            recorded_count=len(changed),
            unchanged_count=len(observations) - len(changed),
        )

    def _is_unchanged(self, observation: Observation) -> bool:
        current = self.open_versions.get(observation.key)
        return current is not None and (current.value, current.source_id) == (
            observation.value,
            observation.source_id,
        )
