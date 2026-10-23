import pytest
from pydantic import ValidationError

from ingestion.config import ApiSettings, IngestionSettings, SourceSettings

PERSISTENCE_URL = "http://persistence.test:8001"


@pytest.fixture(autouse=True)
def required_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", PERSISTENCE_URL)
    monkeypatch.setenv("INGESTION_DB__DSN", "oracle.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "not-a-secret")


def test_defaults_are_the_conservative_ecb_values() -> None:
    ecb = IngestionSettings().sources.ecb

    assert ecb == SourceSettings(
        enabled=True,
        max_concurrent_requests=1,
        min_interval_seconds=2.0,
        timeout_seconds=60.0,
        max_attempts=3,
        lookback_business_days=10,
    )


def test_source_settings_come_from_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_SOURCES__ECB__ENABLED", "false")
    monkeypatch.setenv("INGESTION_SOURCES__ECB__MAX_CONCURRENT_REQUESTS", "2")
    monkeypatch.setenv("INGESTION_SOURCES__ECB__MIN_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("INGESTION_SOURCES__ECB__TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("INGESTION_SOURCES__ECB__MAX_ATTEMPTS", "2")

    ecb = IngestionSettings().sources.ecb

    assert not ecb.enabled
    assert ecb.max_concurrent_requests == 2
    assert ecb.min_interval_seconds == 5.0
    assert ecb.timeout_seconds == 30.0
    assert ecb.max_attempts == 2


def test_lookback_and_persistence_come_from_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS", "5")
    monkeypatch.setenv("INGESTION_PERSISTENCE__TIMEOUT_SECONDS", "10")

    settings = IngestionSettings()

    assert settings.sources.ecb.lookback_business_days == 5
    assert str(settings.persistence.url) == PERSISTENCE_URL + "/"
    assert settings.persistence.timeout_seconds == 10.0


def test_the_persistence_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INGESTION_PERSISTENCE__URL")

    with pytest.raises(ValidationError, match="persistence"):
        IngestionSettings()


def test_the_ing_database_comes_from_environment_variables() -> None:
    db = IngestionSettings().db

    assert (db.dsn, db.user, db.password.get_secret_value()) == (
        "oracle.test:1521/FREEPDB1",
        "ing_app",
        "not-a-secret",
    )
    assert "not-a-secret" not in repr(db)


@pytest.mark.parametrize("name", ["INGESTION_DB__DSN", "INGESTION_DB__PASSWORD"])
def test_the_ing_database_is_required(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError, match="db"):
        IngestionSettings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("INGESTION_SOURCES__ECB__MAX_ATTEMPTS", "4"),
        ("INGESTION_SOURCES__ECB__MAX_CONCURRENT_REQUESTS", "0"),
        ("INGESTION_SOURCES__ECB__MIN_INTERVAL", "2"),
        ("INGESTION_SOURCES__UNKNOWN__ENABLED", "true"),
        ("INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS", "-1"),
        ("INGESTION_PERSISTENCE__URL", "not a url"),
    ],
)
def test_invalid_or_unknown_settings_fail_at_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        IngestionSettings()


def test_api_settings_read_the_nested_db_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGESTION_DB__DSN", "api.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "api-secret")
    monkeypatch.setenv("INGESTION_DB__POOL_MAX", "8")

    db = ApiSettings().db

    assert (db.dsn, db.user, db.password.get_secret_value(), db.pool_max) == (
        "api.test:1521/FREEPDB1",
        "ing_app",
        "api-secret",
        8,
    )


def test_api_settings_need_no_persistence_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INGESTION_PERSISTENCE__URL", raising=False)
    monkeypatch.setenv("INGESTION_DB__DSN", "api.test:1521/FREEPDB1")
    monkeypatch.setenv("INGESTION_DB__PASSWORD", "api-secret")

    ApiSettings()


def test_for_source_returns_the_slot_of_the_source() -> None:
    sources = IngestionSettings().sources

    assert sources.for_source("ecb") == sources.ecb


def test_for_source_rejects_an_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown source 'nope'"):
        IngestionSettings().sources.for_source("nope")
