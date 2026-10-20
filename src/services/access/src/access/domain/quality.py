"""Quality status attached to published values in access answers."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class QualityStatus(StrEnum):
    PASSED = "passed"
    INFO = "info"
    WARN = "warn"
    UNCHECKED = "unchecked"


class Severity(StrEnum):
    INFO = "info"
    WARN = "warn"


@dataclass(frozen=True, slots=True)
class QualityFlag:
    rule: str
    severity: Severity
    explanation: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ValueQuality:
    status: QualityStatus
    flags: tuple[QualityFlag, ...] = ()


UNCHECKED = ValueQuality(status=QualityStatus.UNCHECKED, flags=())


def quality_for(version_id: int, known: Mapping[int, ValueQuality] | None) -> ValueQuality:
    """The quality of one value; unknown results are ``unchecked``."""
    if known is None or version_id not in known:
        return UNCHECKED
    return known[version_id]


def quality_is_complete(
    version_ids: Iterable[int], known: Mapping[int, ValueQuality] | None
) -> bool:
    """True when every value has a known result that is not ``unchecked``."""
    ids = set(version_ids)
    if known is None or not ids <= known.keys():
        return False
    return all(known[version_id].status != QualityStatus.UNCHECKED for version_id in ids)
