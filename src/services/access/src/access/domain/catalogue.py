"""The curve catalogue as access reads it; persistence owns the catalogue."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridMaturity:
    maturity: str
    months: int


@dataclass(frozen=True, slots=True)
class CurveDefinition:
    curve_id: str
    label: str
    source_id: str
    area: str
    attribution: str
    rate_type: str
    compounding: str
    unit: str
    source_model: str | None
    simulated: bool
    maturities: tuple[GridMaturity, ...]
