"""Read interface of the persistence service: what changed in a curve between two knowledge times.

A consumer asks for the published values of a curve between two valid dates
(inclusive), comparing the state known at ``meta.since`` with the state known at
``meta.as_of``. Each change is a value whose visible version differs between the
two states: a changed value, or a value known only at ``meta.as_of``, which has no
``old_value``. Changes are compared state to state, so a value changed and changed
back shows its old and new value as equal with the reason of its latest version.
Changes are ordered by valid date and the grid order of the maturity.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.persistence.v1.observations import ChangeReason

CURVE_CHANGES_PATH = "/v1/curves/{curve_id}/changes"
"""``GET`` endpoint that returns the values of a curve that changed between two knowledge times."""


class ValueChange(BaseModel):
    """One published value whose visible version differs between the two knowledge times."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_date: date = Field(description="Valid time: the business date of the value")
    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    old_value: float | None = Field(
        allow_inf_nan=False,
        description="Yield in percent known at meta.since; null when the value was not known then",
        examples=[2.61],
    )
    new_value: float = Field(
        allow_inf_nan=False,
        description="Yield in percent known at meta.as_of",
        examples=[2.7],
    )
    change_reason: ChangeReason = Field(description="Reason of the version known at meta.as_of")
    source_id: str | None = Field(min_length=1, max_length=64, examples=["ecb"])
    known_from: AwareDatetime = Field(
        description="Knowledge time (UTC) the version known at meta.as_of became known"
    )


class CurveChanges(BaseModel):
    """The changes of one curve over a range of valid dates, in valid-date and grid order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    valid_from: date = Field(description="Valid time: first valid date of the range (inclusive)")
    valid_to: date = Field(description="Valid time: last valid date of the range (inclusive)")
    changes: list[ValueChange]


class ChangesMeta(BaseModel):
    """The two knowledge times the changes were determined between."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    since: AwareDatetime = Field(description="Earlier knowledge time (UTC) of the comparison")
    as_of: AwareDatetime = Field(description="Later knowledge time (UTC) of the comparison")


class CurveChangesResponse(BaseModel):
    """Body of ``GET`` on the :data:`CURVE_CHANGES_PATH` endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: CurveChanges
    meta: ChangesMeta
