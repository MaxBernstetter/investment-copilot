import pytest
from pydantic import ValidationError

from persistence.config import Settings


def test_reads_the_database_settings_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERSISTENCE_DB_DSN", "oracle:1521/FREEPDB1")
    monkeypatch.setenv("PERSISTENCE_DB_PASSWORD", "app-password")
    monkeypatch.setenv("PERSISTENCE_DB_POOL_MAX", "8")

    settings = Settings()

    assert settings.db_dsn == "oracle:1521/FREEPDB1"
    assert settings.db_user == "core_app"
    assert settings.db_password.get_secret_value() == "app-password"
    assert settings.db_pool_max == 8


def test_fails_fast_without_database_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PERSISTENCE_DB_DSN", raising=False)
    monkeypatch.delenv("PERSISTENCE_DB_PASSWORD", raising=False)

    with pytest.raises(ValidationError, match="db_password"):
        Settings()
