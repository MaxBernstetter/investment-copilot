"""Quality status on published values and per-day quality reads in access responses."""

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

QUALITY_PATH = "/v1/curves/{curve_id}/quality"
"""``GET`` endpoint that returns the quality status of each valid date of a curve."""


class QualityStatus(StrEnum):
    """Outcome of checks: ``unchecked`` means no result is known for the value."""

    PASSED = "passed"
    INFO = "info"
    WARN = "warn"
    UNCHECKED = "unchecked"


class Severity(StrEnum):
    """How serious a flag is: ``warn`` is shown as a warning, ``info`` as a note."""

    WARN = "warn"
    INFO = "info"


class QualityFlag(BaseModel):
    """One rule finding on a published value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str = Field(
        min_length=1,
        description="Plausibility or completeness rule that produced the flag",
        examples=["range"],
    )
    severity: Severity
    explanation: str = Field(description="Why the rule exists, in user language")
    evidence: str = Field(description="What was found, with the numbers")


class ValueQuality(BaseModel):
    """Quality of one published value, with the flags that apply to it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: QualityStatus
    flags: list[QualityFlag] = Field(
        description="Rule findings on this value; empty when status is passed or unchecked"
    )


class Rule(StrEnum):
    """A plausibility or completeness rule of the processing service."""

    RANGE = "range"
    JUMP = "jump"
    MISSING_DATE = "missing-date"
    MISSING_MATURITY = "missing-maturity"


class QualityFinding(BaseModel):
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
    findings: list[QualityFinding]


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
    source_attribution: str = Field(
        description="Required attribution of the source values (ESCB reuse terms); "
        "for simulated data a note that it is simulated",
        examples=["Source: ECB statistics"],
    )


class QualityDaysResponse(BaseModel):
    """Body of ``GET /v1/curves/{curve_id}/quality``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: QualityDays
    meta: QualityMeta
