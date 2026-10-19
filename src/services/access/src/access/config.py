"""Configuration from environment variables (prefix ``ACCESS_``), validated at startup."""

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ACCESS_", frozen=True)

    persistence_url: AnyHttpUrl = Field(description="Base URL of the persistence api")
    persistence_timeout_seconds: float = Field(default=10.0, gt=0)
    cors_origins: str = Field(
        default="http://localhost:5174",
        description="Comma-separated origins allowed to call the API (the frontend)",
    )

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
