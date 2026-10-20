"""Run history shapes of the transparency interface, version 1."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

RUNS_PATH = "/v1/runs"
"""``GET`` endpoint that lists run attempts of a service, newest first."""

RUN_PATH = "/v1/runs/{run_id}"
"""``GET`` endpoint that returns every attempt of one run id."""

DEFAULT_RUNS_LIMIT = 50
"""Default page size for ``GET /v1/runs``."""

MAX_RUNS_LIMIT = 200
"""Largest page size ``GET /v1/runs`` accepts."""


class RunStatus(StrEnum):
    """Outcome of a run attempt after it has finished, or ``running`` while it is open."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    """failed after at least one step was committed"""
    FAILED = "failed"


class Run(BaseModel):
    """One attempt of a run of a service."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=128, examples=["daily_load_ecb-2026-10-16"])
    attempt: int = Field(ge=1)
    service: str = Field(min_length=1, max_length=32, examples=["ingestion"])
    operation: str = Field(min_length=1, max_length=32, examples=["daily"])
    status: RunStatus
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    delivered_count: int = Field(ge=0, description="Observations the source delivered")
    recorded_count: int = Field(ge=0, description="New versions stored")
    unchanged_count: int = Field(ge=0, description="Values already stored unchanged")
    error_type: str | None = Field(default=None, max_length=128)
    error_message: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def finished_times_match_status(self) -> "Run":
        running = self.status == RunStatus.RUNNING
        finish_set = self.finished_at is not None
        duration_set = self.duration_seconds is not None
        if running:
            if finish_set or duration_set:
                raise ValueError(
                    "finished_at and duration_seconds are null exactly while the attempt is running"
                )
        elif not finish_set or not duration_set:
            raise ValueError(
                "finished_at and duration_seconds are null exactly while the attempt is running"
            )
        return self


class RunsMeta(BaseModel):
    """Pagination metadata for a run list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    next_cursor: str | None = Field(
        default=None,
        description="Pass as `cursor` for the next page; null on the last page",
    )


class RunsResponse(BaseModel):
    """Body of ``GET /v1/runs``, newest first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: list[Run]
    meta: RunsMeta


class RunAttemptsResponse(BaseModel):
    """Body of ``GET /v1/runs/{run_id}``: every attempt, in attempt order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: list[Run]
