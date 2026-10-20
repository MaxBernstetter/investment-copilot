"""Public read interface of the access service: one maturity of a curve over valid dates.

The shape mirrors the persistence read interface, but the public contract is versioned on
its own: the frontend depends on this module, not on the persistence contract. Points come
in valid-date order; a valid date without a published value known as of ``meta.as_of`` has
no point, so the series has gaps rather than null values.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from contracts.access.v1.curves import CurveMeta, Origin

SERIES_OBSERVATIONS_PATH = "/v1/curves/{curve_id}/maturities/{maturity}/observations"
"""``GET`` endpoint that returns one maturity of a curve over valid dates."""


class SeriesPoint(BaseModel):
    """One valid date with a published value known as of ``meta.as_of``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_date: date = Field(description="Valid time: the business date of the value")
    value: float = Field(allow_inf_nan=False, description="Yield in percent", examples=[2.61])
    version_id: int = Field(
        description="Version id of the visible version, the lineage reference: the version_id "
        "the versions endpoint lists for this value"
    )
    origin: Origin = Field(
        description="published: the source value, unmodified; derived: computed by the service "
        "(none yet)"
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
