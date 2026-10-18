"""Ingestion settings, read from environment variables and validated at startup.

Naming scheme: ``INGESTION_<FIELD>``, nested with ``__``. Per-source access settings
are ``INGESTION_SOURCES__<SOURCE>__<SETTING>``, for example
``INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS=2``. Unknown sources or settings are
rejected, so a typo fails at startup instead of being ignored.
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_ATTEMPTS_PER_REQUEST = 3
"""Upper bound from the source access policy: at most 3 attempts per request."""


class SourceSettings(BaseModel):
    """Access settings for one source (see the source access policy).

    The defaults are the conservative values used for the ECB, which publishes no limit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    """Kill switch: when false, the client refuses every request to the source."""
    max_concurrent_requests: int = Field(default=1, ge=1)
    min_interval_seconds: float = Field(default=2.0, ge=0)
    """Minimum time between the starts of two requests (attempts) to the source."""
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_attempts: int = Field(default=MAX_ATTEMPTS_PER_REQUEST, ge=1, le=MAX_ATTEMPTS_PER_REQUEST)
    backoff_base_seconds: float = Field(default=1.0, gt=0)
    """Backoff before retry n is ``base * 2**(n-1)``, with jitter."""
    max_retry_after_seconds: float = Field(default=120.0, ge=0)
    """A ``Retry-After`` longer than this is not waited for: the request fails instead."""


class SourcesSettings(BaseModel):
    """One entry per supported source. Adding a source adds a field here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ecb: SourceSettings = SourceSettings()


class IngestionSettings(BaseSettings):
    """All ingestion settings. Construct once at process start."""

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    sources: SourcesSettings = SourcesSettings()
