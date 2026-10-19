"""The version history of one value as the access service reads it."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ChangeReason(StrEnum):
    """Why a version exists."""

    INITIAL = "initial"
    REVISION = "revision"
    CORRECTION = "correction"
    RECALCULATION = "recalculation"
    SIMULATED = "simulated"


@dataclass(frozen=True, slots=True)
class ValueVersion:
    """One stored version of a value, with its knowledge interval and provenance."""

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
    """One value's versions, oldest first, as they were known at ``as_of``."""

    curve_id: str
    maturity: str
    valid_date: date
    as_of: datetime
    versions: tuple[ValueVersion, ...]
