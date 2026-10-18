"""Observations and their versions in the bitemporal core.

An observation is a yield for a curve, maturity and valid date (valid time).
Each recorded version also carries a knowledge time: the instant from which
the platform knew it. The database sets the knowledge time, so the domain
only describes what is to be recorded.

Versions are never overwritten: recording a changed value (or source) closes
the open version and opens a new one; recording an unchanged one is a no-op.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class Origin(StrEnum):
    PUBLISHED = "published"
    DERIVED = "derived"


class ChangeReason(StrEnum):
    INITIAL = "initial"
    REVISION = "revision"
    CORRECTION = "correction"
    RECALCULATION = "recalculation"
    SIMULATED = "simulated"


class InvalidObservationsError(ValueError):
    """A batch of observations breaks a domain rule; nothing was recorded."""


class OpenVersionExistsError(Exception):
    """A concurrent write opened a version of an observation of the batch first.

    Nothing was recorded; recording the batch again resolves it.
    """


@dataclass(frozen=True, slots=True)
class ObservationKey:
    """Identifies an observation; at most one version per key is open at a time."""

    curve_id: str
    maturity: str
    valid_date: date
    origin: Origin
    method_version: str | None


@dataclass(frozen=True, slots=True)
class Observation:
    curve_id: str
    maturity: str
    valid_date: date
    value: Decimal
    origin: Origin
    method_version: str | None
    source_id: str | None
    run_id: str
    change_reason: ChangeReason

    def __post_init__(self) -> None:
        if (self.origin is Origin.DERIVED) != (self.method_version is not None):
            raise InvalidObservationsError(
                "a derived observation needs a method version; a published one has none"
            )

    @property
    def key(self) -> ObservationKey:
        return ObservationKey(
            self.curve_id, self.maturity, self.valid_date, self.origin, self.method_version
        )


@dataclass(frozen=True, slots=True)
class RecordedVersions:
    """Outcome of recording a batch: all its new versions share one knowledge time.

    ``recorded_count`` counts the new versions; ``unchanged_count`` the
    observations whose open version already had the same value and source.
    """

    known_from: datetime
    recorded_count: int
    unchanged_count: int


def ensure_unique_keys(observations: Iterable[Observation]) -> None:
    """A batch may describe each observation only once."""
    duplicates = [key for key, count in Counter(o.key for o in observations).items() if count > 1]
    if duplicates:
        examples = ", ".join(_describe(key) for key in duplicates[:3])
        raise InvalidObservationsError(
            f"{len(duplicates)} observation(s) appear more than once, e.g. {examples}"
        )


def _describe(key: ObservationKey) -> str:
    method = f"/{key.method_version}" if key.method_version else ""
    return f"{key.curve_id} {key.maturity} {key.valid_date.isoformat()} {key.origin}{method}"
