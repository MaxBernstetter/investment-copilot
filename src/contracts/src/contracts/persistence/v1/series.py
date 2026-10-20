"""Read interface of the persistence service: one maturity of a curve over a range of valid dates.

A consumer asks for one maturity of a curve between two valid dates (inclusive)
as it was known at ``meta.as_of``. Only published values count; a value is visible
when its knowledge interval contains ``as_of``, so a later revision never changes
an answer for an earlier time. Points come in valid-date order, and a valid date
without a visible published value is left out, which leaves a gap in the series.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from contracts.persistence.v1.curves import CurveMeta

SERIES_OBSERVATIONS_PATH = "/v1/curves/{curve_id}/maturities/{maturity}/observations"
"""``GET`` endpoint that returns one maturity of a curve over a range of valid dates."""


class SeriesPoint(BaseModel):
    """One valid date of a series with a published value known at ``meta.as_of``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_date: date = Field(description="Valid time: the business date of the value")
    value: float = Field(
        allow_inf_nan=False,
        description="Yield in percent",
        examples=[2.61],
    )
    version_id: int = Field(
        description="Version id of the visible version, the lineage reference",
        examples=[4711],
    )


class SeriesObservations(BaseModel):
    """One maturity of a curve, with its points in valid-date order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    points: list[SeriesPoint]


class SeriesObservationsResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/maturities/{maturity}/observations``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: SeriesObservations
    meta: CurveMeta
