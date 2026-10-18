import pytest
from pydantic import ValidationError

from ingestion.config import IngestionSettings, SourceSettings


def test_defaults_are_the_conservative_ecb_values() -> None:
    ecb = IngestionSettings().sources.ecb

    assert ecb == SourceSettings(
        enabled=True,
        max_concurrent_requests=1,
        min_interval_seconds=2.0,
        timeout_seconds=60.0,
        max_attempts=3,
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


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("INGESTION_SOURCES__ECB__MAX_ATTEMPTS", "4"),
        ("INGESTION_SOURCES__ECB__MAX_CONCURRENT_REQUESTS", "0"),
        ("INGESTION_SOURCES__ECB__MIN_INTERVAL", "2"),
        ("INGESTION_SOURCES__UNKNOWN__ENABLED", "true"),
    ],
)
def test_invalid_or_unknown_settings_fail_at_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        IngestionSettings()
