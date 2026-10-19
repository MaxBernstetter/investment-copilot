import pytest
from pydantic import ValidationError

from access.config import Settings


def test_requires_the_persistence_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCESS_PERSISTENCE_URL", raising=False)

    with pytest.raises(ValidationError, match="persistence_url"):
        Settings()


def test_cors_origins_default_to_the_vite_dev_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESS_PERSISTENCE_URL", "http://persistence:8001")
    monkeypatch.delenv("ACCESS_CORS_ORIGINS", raising=False)

    assert Settings().cors_origin_list() == ["http://localhost:5174"]


def test_cors_origins_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESS_PERSISTENCE_URL", "http://persistence:8001")
    monkeypatch.setenv("ACCESS_CORS_ORIGINS", " https://a.example , https://b.example,,")

    assert Settings().cors_origin_list() == ["https://a.example", "https://b.example"]
