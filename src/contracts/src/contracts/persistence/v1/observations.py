"""Write interface of the persistence service: record observation versions.

Consumers (ingestion, processing) send a batch of observations; persistence
stores each one as a new version with valid time (``valid_date``) and
knowledge time (``known_from``, set by the database clock).
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

RECORD_VERSIONS_PATH = "/v1/observations/versions"
"""``POST`` endpoint that records a batch of observation versions."""

MAX_BATCH_SIZE = 10_000
"""Upper bound of observations per request; larger loads are split into chunks."""


class Origin(StrEnum):
    """Whether a value was published by a source or derived by YieldLens."""

    PUBLISHED = "published"
    DERIVED = "derived"


class ChangeReason(StrEnum):
    """Why a version exists."""

    INITIAL = "initial"
    REVISION = "revision"
    CORRECTION = "correction"
    RECALCULATION = "recalculation"
    SIMULATED = "simulated"


class ObservationVersion(BaseModel):
    """One yield for a curve, maturity and valid date, to be recorded as a version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    maturity: str = Field(
        pattern=r"^([1-9][0-9]*[DWMY])+$",
        max_length=16,
        description="Tenor code, e.g. 3M, 10Y or 1Y6M",
        examples=["10Y"],
    )
    valid_date: date = Field(description="Valid time: the business date the value applies to")
    value: Decimal = Field(
        allow_inf_nan=False, max_digits=38, description="The yield in percent", examples=["2.6"]
    )
    origin: Origin
    method_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Required for derived values, absent for published ones",
    )
    source_id: str | None = Field(default=None, min_length=1, max_length=64, examples=["ecb"])
    run_id: str = Field(min_length=1, max_length=128, description="Run that produced the value")
    change_reason: ChangeReason

    @model_validator(mode="after")
    def _method_version_matches_origin(self) -> Self:
        if (self.origin is Origin.DERIVED) != (self.method_version is not None):
            raise ValueError("method_version is required for derived and forbidden for published")
        return self


class RecordVersionsRequest(BaseModel):
    """Body of ``POST /v1/observations/versions``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observations: list[ObservationVersion] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class RecordVersionsResponse(BaseModel):
    """Result of recording a batch: every version shares one knowledge time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recorded_count: int = Field(ge=0, description="Number of versions stored")
    known_from: AwareDatetime = Field(description="Knowledge time (UTC) of the recorded versions")
