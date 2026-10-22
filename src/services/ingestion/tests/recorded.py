"""Recorded ECB responses (``tests/fixtures/ecb``); see ``recordings.json`` for how."""

import json
from pathlib import Path
from typing import Any

import httpx

ECB_FIXTURES = Path(__file__).parent / "fixtures" / "ecb"

DAILY = "daily_2026-10-01_2026-10-15.csv"
EMPTY_WINDOW = "empty_2026-10-10_2026-10-11.csv"
NO_SERIES_404 = "no_series_updated_after_2026-10-18.json"
HISTORY_2025 = "history_2025-12-22_2025-12-31.csv"
HISTORY_2026 = "history_2026-01-01_2026-01-09.csv"
MALFORMED = "malformed_2026-10-01_2026-10-15.csv"
"""Crafted from ``DAILY``: one non-ISO date and one non-numeric value."""
MIXED = "mixed_2026-10-14_2026-10-15.csv"
"""Both curves (G_N_A+G_N_C) for two days: 2 x 11 x 2 rows."""


def payload(name: str) -> bytes:
    return (ECB_FIXTURES / name).read_bytes()


def recorded_response(name: str) -> httpx.Response:
    """The recorded answer as an ``httpx.Response`` (crafted files answer like ``DAILY``)."""
    recordings: dict[str, Any] = json.loads((ECB_FIXTURES / "recordings.json").read_text())
    recording = recordings.get(name, recordings[DAILY])
    return httpx.Response(
        recording["status"],
        content=payload(name),
        headers={
            "Content-Type": recording["content_type"],
            "Last-Modified": recording["last_modified"],
        },
    )
