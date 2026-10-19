"""The version history of one value as it was known at a knowledge time.

A version is one stored state of a published value, with the knowledge interval
it was current for. Versions first known after ``as_of`` are not part of the
history; ``known_to`` is None while a version is still current at ``as_of``.
"""

from dataclasses import dataclass
from datetime import date, datetime

from persistence.domain.observation import ChangeReason


@dataclass(frozen=True, slots=True)
class ValueVersion:
    version_id: int
    value: float
    known_from: datetime
    known_to: datetime | None
    source_id: str | None
    run_id: str
    change_reason: ChangeReason
    normalization_version: str | None
    delivery_id: str | None


@dataclass(frozen=True, slots=True)
class ValueVersions:
    curve_id: str
    maturity: str
    valid_date: date
    as_of: datetime
    versions: tuple[ValueVersion, ...]
