"""Derived measures of the processing service: spreads, curvature and inversion of a curve.

A consumer asks for the measures of one curve over a range of valid dates
(``MEASURES_PATH``). Each valid date with at least one known input becomes one point.
Measures are computed on read from the inputs (3M, 2Y, 5Y and 10Y) as known at
``meta.as_of`` (UTC), so nothing is stored. Units: the spreads and the curvature are in
basis points (1 bp = 0.01 percentage points); the inputs are yields in percent.

A measure is ``null`` when one of its inputs is missing; ``missing`` lists those inputs and
no value is interpolated. ``inverted`` is true when the 2Y-10Y spread is below zero.
``quality`` is the worst status of the inputs; ``flagged`` lists the inputs with a warn or
info status. ``meta.method_version`` identifies the formulas and the input set.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.processing.v1.quality import QualityStatus

MEASURES_PATH = "/v1/curves/{curve_id}/measures"
"""``GET`` endpoint that returns the derived measures of a curve per valid date."""

MAX_MEASURES_RANGE = 3660
"""Largest number of valid dates one measures request may span."""


class MeasureInput(BaseModel):
    """One input yield of a point, with the lineage and quality of the value used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    value: float = Field(allow_inf_nan=False, description="Yield in percent", examples=[2.61])
    version_id: int = Field(description="Lineage reference of the value")
    status: QualityStatus


class MeasureQuality(BaseModel):
    """Quality of a point: the worst status of its inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: QualityStatus
    flagged: list[str] = Field(description="Input maturities with a warn or info status")


class MeasurePoint(BaseModel):
    """The derived measures of one valid date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_date: date = Field(description="Valid time: the business date of the point")
    spread_2y_10y: float | None = Field(
        allow_inf_nan=False,
        description="The slope: 10Y minus 2Y, in basis points; null when an input is missing",
        examples=[66.0],
    )
    spread_3m_10y: float | None = Field(
        allow_inf_nan=False,
        description="10Y minus 3M, in basis points; null when an input is missing",
        examples=[71.0],
    )
    curvature_2y_5y_10y: float | None = Field(
        allow_inf_nan=False,
        description="2 times 5Y minus 2Y and 10Y, in basis points; null when an input is missing",
        examples=[-20.0],
    )
    inverted: bool | None = Field(
        description="The slope is below zero; null when the slope is null"
    )
    inputs: list[MeasureInput] = Field(description="The inputs present, in 3M, 2Y, 5Y, 10Y order")
    missing: list[str] = Field(description="The inputs absent, in 3M, 2Y, 5Y, 10Y order")
    quality: MeasureQuality


class CurveMeasures(BaseModel):
    """Derived measures of a curve over a range of valid dates, in valid-date order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    valid_from: date = Field(description="Valid time: first valid date of the range (inclusive)")
    valid_to: date = Field(description="Valid time: last valid date of the range (inclusive)")
    points: list[MeasurePoint]


class MeasuresMeta(BaseModel):
    """How the measures were determined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: AwareDatetime = Field(
        description="The effective knowledge time (UTC) of the inputs and their quality"
    )
    method_version: str = Field(
        min_length=1, description="Version of the measure definitions", examples=["1"]
    )


class MeasuresResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/measures``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: CurveMeasures
    meta: MeasuresMeta
