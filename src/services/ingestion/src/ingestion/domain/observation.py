"""Published observations as a source delivers them."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PublishedObservation:
    """One value of a published curve, exactly as the source delivered it."""

    curve_id: str
    maturity: str
    """Tenor code, e.g. ``3M`` or ``10Y``."""
    valid_date: date
    value: Decimal
    """In the source's unit (ECB: percent per annum), unchanged."""
    normalization_version: str
    """Version of the source mapping (normalization rules) that produced this observation."""
