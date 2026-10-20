"""Alert shapes of the transparency interface, version 1."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

ALERTS_PATH = "/v1/alerts"
"""``GET`` endpoint that lists active and recent business alerts of a service."""


class AlertSeverity(StrEnum):
    """How serious an alert is."""

    CRITICAL = "critical"
    WARNING = "warning"


class Alert(BaseModel):
    """One business alert raised by a service."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alert_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=64, examples=["run_failed"])
    severity: AlertSeverity
    since: AwareDatetime
    cleared_at: AwareDatetime | None
    acknowledged_at: AwareDatetime | None
    run_id: str | None = Field(default=None, max_length=128)
    attempt: int | None = Field(default=None, ge=1)
    cause: str | None = Field(
        default=None,
        max_length=4000,
        description="Error type and message of the attempt that raised the alert",
    )


class AlertsResponse(BaseModel):
    """Body of ``GET /v1/alerts``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: list[Alert]
