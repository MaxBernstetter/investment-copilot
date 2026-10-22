"""Derived measures of the access service: spreads, curvature and inversion of a curve.

The access service relays the measures that processing computes, with the same field names
and units (spreads and curvature in basis points, inputs in percent). ``meta.as_of`` is the
knowledge time of the inputs and their quality; ``meta.method_version`` identifies the formulas
and the input set; ``meta.source_attribution`` is the attribution of the source values.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.access.v1.quality import QualityStatus

MEASURES_PATH = "/v1/curves/{curve_id}/measures"
"""``GET`` endpoint that returns the derived measures of a curve per valid date."""


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
    source_attribution: str = Field(
        description="Required attribution of the source values (ESCB reuse terms); "
        "for simulated data a note that it is simulated",
        examples=["Source: ECB statistics"],
    )


class MeasuresResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/measures``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: CurveMeasures
    meta: MeasuresMeta
