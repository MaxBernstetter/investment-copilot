"""Quality status on published values in access responses."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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
