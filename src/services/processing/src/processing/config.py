"""Configuration from environment variables (prefix ``PROCESSING_``), validated at startup.

Nested values use ``__``, for example ``PROCESSING_DB__DSN`` and ``PROCESSING_DB__PASSWORD``.
"""

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dsn: str = Field(min_length=1, description="Oracle DSN, e.g. localhost:1521/FREEPDB1")
    user: str = Field(default="proc_app", min_length=1)
    password: SecretStr
    pool_min: int = Field(default=1, ge=0)
    pool_max: int = Field(default=4, ge=1)
    acquire_timeout_ms: int = Field(default=5_000, gt=0)
    call_timeout_ms: int = Field(default=30_000, gt=0)


class PersistenceSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: AnyHttpUrl
    timeout_seconds: float = Field(default=30.0, gt=0)


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROCESSING_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    db: DatabaseSettings


class JobSettings(BaseSettings):
    """Settings for the ``processing-check-quality`` job (database and persistence reads)."""

    model_config = SettingsConfigDict(
        env_prefix="PROCESSING_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    db: DatabaseSettings
    persistence: PersistenceSettings
