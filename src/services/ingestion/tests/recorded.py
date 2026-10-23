"""Recorded ECB and US Treasury responses (``tests/fixtures/ecb``, ``tests/fixtures/ust``); see
``recordings.json`` in each for how they were recorded."""

import json
from pathlib import Path
from typing import Any

import httpx

ECB_FIXTURES = Path(__file__).parent / "fixtures" / "ecb"
UST_FIXTURES = Path(__file__).parent / "fixtures" / "ust"

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


UST_YEAR_1990 = "year_1990_head.csv"
"""Recorded: 9 columns, no 20 Yr."""
UST_YEAR_2004 = "year_2004_head.csv"
"""Recorded: no 30 Yr."""
UST_YEAR_2025 = "year_2025_head.csv"
"""Recorded: 14 columns, empty 1.5 Month cells in early January."""
UST_EMPTY_2027 = "empty_2027.csv"
"""Recorded: HTTP 200 with an empty body."""
UST_NEW_COLUMN_2025 = "new_column_2025.csv"
"""Crafted from ``UST_YEAR_2025``: an unknown column ``9 Mo``."""
UST_MISSING_COLUMN_2025 = "missing_column_2025.csv"
"""Crafted from ``UST_YEAR_2025``: the required column ``6 Mo`` is gone."""
UST_MALFORMED_2025 = "malformed_2025.csv"
"""Crafted from ``UST_YEAR_2025``: an ISO date and a value ``n/a``."""


def ust_payload(name: str) -> bytes:
    return (UST_FIXTURES / name).read_bytes()


def ust_response(name: str) -> httpx.Response:
    """The recorded (or crafted) answer as an ``httpx.Response``."""
    recordings: dict[str, Any] = json.loads((UST_FIXTURES / "recordings.json").read_text())
    recording = recordings[name]
    return httpx.Response(
        recording["status"],
        content=ust_payload(name),
        headers={"Content-Type": recording["content_type"]},
    )
