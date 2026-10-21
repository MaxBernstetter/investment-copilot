from pathlib import Path

from processing.domain.explanations import (
    JUMP_INFO,
    JUMP_WARN,
    MISSING_DATE,
    MISSING_MATURITY,
    RANGE_WARN,
)

# tests/unit/domain/ -> the repository root is six levels up from this file.
NOTE = (
    Path(__file__).resolve().parents[6]
    / "docs/project/02-data-processing/01-plausibility-thresholds.md"
)


def test_every_explanation_appears_word_for_word_in_how_users_see_it() -> None:
    text = NOTE.read_text(encoding="utf-8")
    section = text.split("## How users see it", 1)[1].split("\n## ", 1)[0]

    for explanation in (RANGE_WARN, JUMP_INFO, JUMP_WARN, MISSING_DATE, MISSING_MATURITY):
        assert explanation in section
