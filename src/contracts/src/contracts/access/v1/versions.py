"""Public read interface of the access service: the version history of one value.

The shape mirrors the persistence read interface, but the public contract is versioned on
its own: the frontend depends on this module, not on the persistence contract. Versions are
listed oldest first, each with its knowledge interval; ``known_to`` is null while the version
is still current at ``meta.as_of``. Versions first known after ``meta.as_of`` are left out.
"""

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.access.v1.curves import CurveMeta

VALUE_VERSIONS_PATH = (
    "/v1/curves/{curve_id}/maturities/{maturity}/observations/{valid_date}/versions"
)
"""``GET`` endpoint that returns the version history of one value as of a knowledge time."""


class ChangeReason(StrEnum):
    """Why a version exists."""

    INITIAL = "initial"
    REVISION = "revision"
    CORRECTION = "correction"
    RECALCULATION = "recalculation"
    SIMULATED = "simulated"


class ValueVersion(BaseModel):
    """One stored version of a value, with its knowledge interval and provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version_id: int = Field(description="Surrogate key of the version", examples=[4711])
    value: float = Field(allow_inf_nan=False, description="Yield in percent", examples=[2.61])
    known_from: AwareDatetime = Field(description="Knowledge time (UTC) the version became known")
    known_to: AwareDatetime | None = Field(
        description="Knowledge time (UTC) the version stopped being current; "
        "null while it is still current as of meta.as_of"
    )
    source_id: str | None = Field(min_length=1, max_length=64, examples=["ecb"])
    run_id: str = Field(min_length=1, max_length=128, description="Run that wrote the version")
    change_reason: ChangeReason
    normalization_version: str | None = Field(
        min_length=1,
        max_length=64,
        description="Version of the source mapping that produced the value",
        examples=["1"],
    )
    delivery_id: str | None = Field(
        min_length=1,
        max_length=64,
        description="Raw source delivery the value came from",
        examples=["4711"],
    )


class ValueVersions(BaseModel):
    """The version history of one value, oldest version first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    valid_date: date = Field(description="Valid time: the business date of the value")
    versions: list[ValueVersion]


class ValueVersionsResponse(BaseModel):
    """Body of ``GET`` on the :data:`VALUE_VERSIONS_PATH` endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: ValueVersions
    meta: CurveMeta
