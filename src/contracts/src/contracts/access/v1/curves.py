"""Public read interface of the access service: one published curve as of a knowledge time.

The shape mirrors the persistence read interface, but the public contract is versioned on
its own: the frontend depends on this module, not on the persistence contract.
"""

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.access.v1.quality import ValueQuality

CURVE_OBSERVATIONS_PATH = "/v1/curves/{curve_id}/observations"
"""``GET`` endpoint that returns one curve as of a knowledge time."""


class Origin(StrEnum):
    """How a value came to be: published by its source, or derived by the service."""

    PUBLISHED = "published"
    DERIVED = "derived"


class CurvePoint(BaseModel):
    """One maturity of a curve on the common grid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maturity: str = Field(description="Tenor code, e.g. 3M, 10Y", examples=["10Y"])
    months: float = Field(
        gt=0,
        description="Tenor length in months, for ordering; fractional for short tenors",
    )
    value: float | None = Field(
        allow_inf_nan=False,
        description="Yield in percent; null if no published value was known as of meta.as_of",
        examples=[2.61],
    )
    version_id: int | None = Field(
        description="Version id of the visible version, the lineage reference: the version_id "
        "the versions endpoint lists for this value; null exactly when value is null",
        examples=[7],
    )
    origin: Origin = Field(
        description="published: the source value, unmodified; derived: computed by the service "
        "(none yet)"
    )
    quality: ValueQuality | None = Field(
        description="Quality status of the value; null exactly when value is null"
    )


class CurveObservations(BaseModel):
    """One curve on one valid date, with its points in grid order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    valid_date: date = Field(description="Valid time: the business date of the curve")
    points: list[CurvePoint]


class CurveMeta(BaseModel):
    """How the answer was determined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: AwareDatetime = Field(
        description="Effective knowledge time (UTC): the requested as_of, or the knowledge "
        "horizon if that is later or no as_of was requested"
    )
    source_attribution: str = Field(
        description="Required attribution of the source values (ESCB reuse terms); "
        "for simulated data a note that it is simulated",
        examples=["Source: ECB statistics"],
    )


class CurveObservationsResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/observations``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: CurveObservations
    meta: CurveMeta


class Problem(BaseModel):
    """RFC 9457 problem details, the body of every error response."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: str
