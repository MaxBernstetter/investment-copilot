"""The changes of a curve between two knowledge states.

A change is a published value whose visible version differs between the state
known at ``since`` and the state known at ``as_of``: a changed value, or a value
known only at ``as_of``, which has no ``old_value``. Changes are compared state to
state, so a value changed and changed back is not a change.
"""

from dataclasses import dataclass
from datetime import date, datetime

from persistence.domain.observation import ChangeReason


@dataclass(frozen=True, slots=True)
class ValueChange:
    valid_date: date
    maturity: str
    old_value: float | None
    new_value: float
    change_reason: ChangeReason
    source_id: str | None
    known_from: datetime


@dataclass(frozen=True, slots=True)
class CurveChanges:
    curve_id: str
    valid_from: date
    valid_to: date
    since: datetime
    as_of: datetime
    changes: tuple[ValueChange, ...]
