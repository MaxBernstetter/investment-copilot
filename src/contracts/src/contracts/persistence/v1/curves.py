"""Read interface of the persistence service: published curves as of a knowledge time.

A consumer asks for one curve on one valid date as it was known at ``meta.as_of``.
Only published values count; a value is visible when its knowledge interval
contains ``as_of``, so a later revision never changes an answer for an earlier
time. Points come in grid order (shortest maturity first), and a maturity with no
visible published value is returned with ``value`` null rather than left out.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

CURVE_OBSERVATIONS_PATH = "/v1/curves/{curve_id}/observations"
"""``GET`` endpoint that returns one curve as of a knowledge time."""


class CurvePoint(BaseModel):
    """One maturity of a curve on the common grid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maturity: str = Field(description="Tenor code, e.g. 3M, 10Y", examples=["10Y"])
    months: int = Field(gt=0, description="Length of the tenor in months, for ordering")
    value: float | None = Field(
        allow_inf_nan=False,
        description="Yield in percent; null if no published value was known as of meta.as_of",
        examples=[2.61],
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
        description="Knowledge time (UTC) the curve was read at; "
        "the database clock if none was requested"
    )


class CurveObservationsResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/observations``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: CurveObservations
    meta: CurveMeta
