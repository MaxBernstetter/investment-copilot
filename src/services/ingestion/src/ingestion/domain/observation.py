"""Published observations as a source delivers them."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ingestion.domain.windows import DateWindow


@dataclass(frozen=True, slots=True)
class PublishedObservation:
    """One value of a published curve, exactly as the source delivered it."""

    curve_id: str
    maturity: str
    """Tenor code, e.g. ``3M`` or ``10Y``."""
    valid_date: date
    value: Decimal
    """In the source's unit (ECB: percent per annum), unchanged."""


@dataclass(frozen=True, slots=True)
class Delivery:
    """What a source delivered for one window."""

    source_id: str
    window: DateWindow
    observations: tuple[PublishedObservation, ...]
    """Empty when the source had no data for the window."""
    last_modified: datetime | None
    """The source's publication time of its latest change: delivery metadata only,
    never the knowledge time (that is when YieldLens stores a value)."""
