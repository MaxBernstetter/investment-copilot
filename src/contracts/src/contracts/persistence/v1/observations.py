"""Write interface of the persistence service: record observation versions.

Consumers (ingestion, processing) send a batch of observations; persistence
stores each new or changed one as a new version with valid time
(``valid_date``) and knowledge time (``known_from``, set by the database
clock). Versions are never overwritten: a changed value or source for the
same observation closes its open version and opens a new one. Sending an
unchanged observation again (same value and source) is an idempotent no-op,
so reloads and lookback windows can be sent as they are. Provenance
(``run_id``, ``change_reason``, ``normalization_version``, ``delivery_id``)
describes how the value was written, not the value, so it never makes a
version on its own.
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
    """Why a version exists.

    Sent by the caller and stored as sent, except for one case: an ``initial``
    version of an observation that already has a version is stored as
    ``revision``. ``correction``, ``recalculation`` and ``simulated`` are stored
    as sent.
    """

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
        pattern=r"^([1-9][0-9]*(\.[0-9]+)?[DWMY])+$",
        max_length=16,
        description="Tenor code, e.g. 3M, 10Y, 1.5M or 1Y6M",
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
    normalization_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Version of the source mapping (normalization rules) that produced a "
        "published value; not version-relevant",
        examples=["1"],
    )
    delivery_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Raw source delivery the value came from (an ingestion reference); "
        "provenance like run_id, so a new delivery of an unchanged value is no change",
        examples=["4711"],
    )

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
    """Result of recording a batch: every new version shares one knowledge time.

    ``recorded_count + unchanged_count`` is the size of the batch.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recorded_count: int = Field(
        ge=0, description="Number of new versions stored (new or changed observations)"
    )
    unchanged_count: int = Field(
        default=0,
        ge=0,
        description="Number of observations whose open version already had the same value "
        "and source; nothing was stored for them",
    )
    known_from: AwareDatetime = Field(
        description="Knowledge time (UTC) of the call; the new versions start at it"
    )
