"""The curve catalogue: what defines a curve and where its values come from.

A curve definition carries its display label, its source and area, the attribution
its values require, its conventions as published and its grid of maturities.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridMaturity:
    maturity: str
    months: float


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
