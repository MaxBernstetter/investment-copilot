"""Read interface of the processing service: quality results per curve.

A consumer asks for the quality of one curve over a range of valid dates, either per
valid date (``QUALITY_DAYS_PATH``) or per published value (``VALUE_QUALITY_PATH``).
Results describe the knowledge time ``meta.as_of`` (UTC); a date or value without a
result known at that time is ``unchecked``, which is never the same as ``passed``.
"""

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

QUALITY_DAYS_PATH = "/v1/curves/{curve_id}/quality"
"""``GET`` endpoint that returns the quality status of each valid date of a curve."""

VALUE_QUALITY_PATH = "/v1/curves/{curve_id}/value-quality"
"""``GET`` endpoint that returns the quality status of each published value of a curve."""

MAX_DAYS_RANGE = 366
"""Largest number of valid dates one quality-per-day request may span."""

MAX_VALUES_RANGE = 3660
"""Largest number of valid dates one value-quality request may span."""


class Rule(StrEnum):
    """A plausibility or completeness rule of the processing service."""

    RANGE = "range"
    JUMP = "jump"
    MISSING_DATE = "missing-date"
    MISSING_MATURITY = "missing-maturity"


class Severity(StrEnum):
    """How serious a finding is: ``warn`` is shown as a warning, ``info`` as a note."""

    WARN = "warn"
    INFO = "info"


class QualityStatus(StrEnum):
    """Outcome of checks: ``unchecked`` means no result is known for the date or value."""

    PASSED = "passed"
    INFO = "info"
    WARN = "warn"
    UNCHECKED = "unchecked"


class Finding(BaseModel):
    """One rule finding on a valid date, or on one published value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Rule
    severity: Severity
    maturity: str | None = Field(default=None, min_length=1, max_length=16, examples=["10Y"])
    version_id: int | None = Field(
        default=None, description="Lineage reference of the value; null for date-level findings"
    )
    value: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="Yield in percent the finding is about, if any",
        examples=[2.61],
    )
    explanation: str = Field(description="Why the rule exists, in user language")
    evidence: str = Field(description="What was found, with the numbers")


class RuleOutcome(BaseModel):
    """Outcome of one rule for one valid date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Rule
    outcome: QualityStatus
    finding_count: int = Field(ge=0)


class QualityDay(BaseModel):
    """Quality of one valid date of a curve, with the rules that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid_date: date = Field(description="Valid time: the business date of the value")
    status: QualityStatus
    run_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Identifier of the check run; null if unchecked",
    )
    checked_as_of: AwareDatetime | None = Field(
        default=None, description="Knowledge time the check run assessed; null if unchecked"
    )
    rules: list[RuleOutcome]
    findings: list[Finding]


class QualityDays(BaseModel):
    """Quality of a curve over a range of valid dates, in valid-date order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    valid_from: date = Field(description="Valid time: first valid date of the range (inclusive)")
    valid_to: date = Field(description="Valid time: last valid date of the range (inclusive)")
    days: list[QualityDay]


class QualityMeta(BaseModel):
    """How the answer was determined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: AwareDatetime = Field(
        description="The effective knowledge time (UTC) the quality results describe"
    )


class QualityDaysResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/quality``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: QualityDays
    meta: QualityMeta


class ValueQuality(BaseModel):
    """Quality of one published value, with the findings that flag it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version_id: int = Field(description="Lineage reference of the value")
    maturity: str = Field(min_length=1, max_length=16, examples=["10Y"])
    valid_date: date = Field(description="Valid time: the business date of the value")
    status: QualityStatus
    flags: list[Finding]


class ValueQualities(BaseModel):
    """Quality of the published values of a curve over a range of valid dates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    curve_id: str = Field(min_length=1, max_length=64, examples=["ecb-aaa-spot"])
    valid_from: date = Field(description="Valid time: first valid date of the range (inclusive)")
    valid_to: date = Field(description="Valid time: last valid date of the range (inclusive)")
    values: list[ValueQuality]


class ValueQualityResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/value-quality``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: ValueQualities
    meta: QualityMeta
