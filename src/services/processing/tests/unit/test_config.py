import pytest
from pydantic import ValidationError

from processing.config import ApiSettings


def test_settings_read_the_nested_db_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_DB__DSN", "oracle.internal:1521/PROC")
    monkeypatch.setenv("PROCESSING_DB__PASSWORD", "from-the-environment")
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence.test:8001")

    settings = ApiSettings()

    assert settings.db.dsn == "oracle.internal:1521/PROC"
    assert settings.db.user == "proc_app"
    assert settings.db.password.get_secret_value() == "from-the-environment"
    assert settings.db.pool_max == 4
    assert settings.db.call_timeout_ms == 30_000


def test_a_missing_password_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_DB__DSN", "localhost:1521/FREEPDB1")
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence.test:8001")
    monkeypatch.delenv("PROCESSING_DB__PASSWORD", raising=False)

    with pytest.raises(ValidationError, match="password"):
        ApiSettings()


def test_the_api_reads_the_persistence_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_DB__DSN", "localhost:1521/FREEPDB1")
    monkeypatch.setenv("PROCESSING_DB__PASSWORD", "not-a-secret")
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence.test:8001")

    settings = ApiSettings()

    assert str(settings.persistence.url) == "http://persistence.test:8001/"
    assert settings.persistence.timeout_seconds == 30.0
