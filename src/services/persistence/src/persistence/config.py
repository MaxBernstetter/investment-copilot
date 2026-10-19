"""Configuration from environment variables (prefix ``PERSISTENCE_``), validated at startup."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PERSISTENCE_", frozen=True)

    db_dsn: str = Field(min_length=1, description="Oracle DSN, e.g. localhost:1521/FREEPDB1")
    db_user: str = Field(default="core_app", min_length=1)
    db_password: SecretStr
    db_pool_min: int = Field(default=1, ge=0)
    db_pool_max: int = Field(default=4, ge=1)
    db_acquire_timeout_ms: int = Field(default=5_000, gt=0)
    db_call_timeout_ms: int = Field(default=30_000, gt=0)
