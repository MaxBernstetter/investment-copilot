from pathlib import Path

from ingestion.facade.rest.openapi import render_openapi

PUBLISHED = Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "ingestion" / "v1.json"


def test_published_openapi_document_is_current() -> None:
    assert PUBLISHED.read_text(encoding="utf-8") == render_openapi(), (
        "the published OpenAPI document is stale; run `task ingestion:openapi`"
    )
