"""Read interface of the access service: the curve catalogue.

Reference data with no as-of time; curves ordered by curve_id, maturities shortest first.
"""

import itertools
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CURVES_PATH = "/v1/curves"
"""``GET`` endpoint that returns the curve catalogue."""


class RateType(StrEnum):
    """What the curve's rates are: zero-coupon, par or forward."""

    SPOT = "spot"
    PAR = "par"
    FORWARD = "forward"


class Compounding(StrEnum):
    """Compounding convention of the curve's values, as published."""

    CONTINUOUS = "continuous"
    ANNUAL = "annual"
    SEMI_ANNUAL = "semi-annual"


class Unit(StrEnum):
    """Unit of the curve's values."""

    PERCENT = "percent"


class GridMaturity(BaseModel):
    """One maturity of a curve's grid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    months: int = Field(gt=0, description="Length of the tenor in months, for ordering")


class CurveDefinition(BaseModel):
    """One curve of the catalogue: its metadata, conventions and grid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    label: str = Field(min_length=1, max_length=128, examples=["ECB euro area AAA spot"])
    source_id: str = Field(
        min_length=1,
        max_length=64,
        description="Source of the values, as in observations; scenario for a simulated curve",
        examples=["ecb"],
    )
    area: str = Field(min_length=1, max_length=64, examples=["Euro area"])
    attribution: str = Field(
        min_length=1,
        max_length=256,
        description="Required attribution of the values (ESCB reuse terms); "
        "for simulated data a note that it is simulated",
        examples=["Source: ECB statistics"],
    )
    rate_type: RateType
    compounding: Compounding
    unit: Unit
    source_model: str | None = Field(
        max_length=64, description="Model the source fitted the curve with; null if none"
    )
    simulated: bool = Field(description="True for a curve of simulated data")
    maturities: list[GridMaturity] = Field(
        min_length=1, description="The curve's grid, shortest maturity first"
    )

    @model_validator(mode="after")
    def _maturities_in_grid_order(self) -> Self:
        months = [maturity.months for maturity in self.maturities]
        if any(later <= earlier for earlier, later in itertools.pairwise(months)):
            raise ValueError("maturities are ordered by months")
        return self


class CurvesResponse(BaseModel):
    """Body of ``GET /v1/curves``; curves ordered by curve_id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: list[CurveDefinition]
