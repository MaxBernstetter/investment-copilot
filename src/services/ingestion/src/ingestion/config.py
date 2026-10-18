"""Ingestion settings, read from environment variables and validated at startup.

Naming scheme: ``INGESTION_<FIELD>``, nested with ``__``. Per-source settings are
``INGESTION_SOURCES__<SOURCE>__<SETTING>``, for example
``INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS=2``; the persistence service is
``INGESTION_PERSISTENCE__<SETTING>``. Unknown sources or settings are
rejected, so a typo fails at startup instead of being ignored.
"""

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_ATTEMPTS_PER_REQUEST = 3
"""Upper bound from the source access policy: at most 3 attempts per request."""


class SourceSettings(BaseModel):
    """Settings for one source: its access policy and its revision lookback.

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
    lookback_business_days: int = Field(default=10, ge=0)
    """A daily load re-fetches this many business days before the valid date."""


class SourcesSettings(BaseModel):
    """One entry per supported source. Adding a source adds a field here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ecb: SourceSettings = SourceSettings()


class PersistenceSettings(BaseModel):
    """Where ingestion writes observations: the persistence service's REST interface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: AnyHttpUrl
    """Base URL, e.g. ``http://localhost:8001``."""
    timeout_seconds: float = Field(default=30.0, gt=0)


class SpoolSettings(BaseModel):
    """Where fetched windows wait while persistence is unavailable: an S3 bucket (Garage)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(pattern=r"^s3://[^/]+/?$")
    """The bucket, e.g. ``s3://ingestion-spool``."""
    endpoint: AnyHttpUrl
    """The S3 API of the object store, e.g. ``http://localhost:3900``."""
    region: str = "garage"
    """Garage's ``s3_region``."""
    access_key_id: str
    secret_access_key: SecretStr


class IngestionSettings(BaseSettings):
    """All ingestion settings. Construct once at process start."""

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    sources: SourcesSettings = SourcesSettings()
    persistence: PersistenceSettings
