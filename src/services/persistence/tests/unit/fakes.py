"""Test doubles and fixtures shared by the unit tests."""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from persistence.domain.curve import CurvePoint
from persistence.domain.observation import (
    ChangeReason,
    Observation,
    ObservationKey,
    Origin,
    RecordedVersions,
)
from persistence.domain.series import SeriesPoint
from persistence.domain.versions import ValueVersion

KNOWN_FROM = datetime(2026, 3, 12, 18, 0, tzinfo=UTC)
NOW = datetime(2026, 3, 13, 9, 0, tzinfo=UTC)

GRID: tuple[tuple[str, int], ...] = (
    ("3M", 3),
    ("6M", 6),
    ("1Y", 12),
    ("2Y", 24),
    ("3Y", 36),
    ("5Y", 60),
    ("7Y", 84),
    ("10Y", 120),
    ("15Y", 180),
    ("20Y", 240),
    ("30Y", 360),
)


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


@dataclass
class FakeCurveReader:
    """Reads published curves like core_observation: values are known from KNOWN_FROM on."""

    now: datetime = NOW
    horizon: datetime = NOW
    known_from: datetime = KNOWN_FROM
    curves: set[str] = field(default_factory=lambda: {"ecb-aaa-spot"})
    values: dict[tuple[str, date], dict[str, float]] = field(default_factory=dict)
    versions: dict[tuple[str, str, date], list[ValueVersion]] = field(default_factory=dict)

    async def current_knowledge_time(self) -> datetime:
        return self.now

    async def knowledge_horizon(self) -> datetime:
        return self.horizon

    async def latest_valid_date(self, curve_id: str, as_of: datetime) -> date | None:
        if as_of < self.known_from:
            return None
        dates = [valid_date for (key, valid_date) in self.values if key == curve_id]
        return max(dates, default=None)

    async def points_as_of(
        self, curve_id: str, valid_date: date, as_of: datetime
    ) -> list[CurvePoint]:
        if curve_id not in self.curves:
            return []
        known = self.values.get((curve_id, valid_date), {}) if as_of >= self.known_from else {}
        return [
            CurvePoint(maturity=maturity, months=months, value=known.get(maturity))
            for maturity, months in GRID
        ]

    async def has_maturity(self, curve_id: str, maturity: str) -> bool:
        return curve_id in self.curves and maturity in {name for name, _ in GRID}

    async def value_versions(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime
    ) -> list[ValueVersion]:
        known = [
            version
            for version in self.versions.get((curve_id, maturity, valid_date), [])
            if version.known_from <= as_of
        ]
        # Like core_observation.get_value_versions: known_to is hidden while still current.
        shown = [
            replace(
                version,
                known_to=None
                if version.known_to is None or version.known_to > as_of
                else version.known_to,
            )
            for version in known
        ]
        return sorted(shown, key=lambda version: version.known_from)

    async def series_as_of(
        self, curve_id: str, maturity: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[SeriesPoint]:
        if as_of < self.known_from:
            return []
        dated = sorted(
            (valid_date, known[maturity])
            for (key, valid_date), known in self.values.items()
            if key == curve_id and maturity in known and valid_from <= valid_date <= valid_to
        )
        return [SeriesPoint(valid_date=valid_date, value=value) for valid_date, value in dated]
