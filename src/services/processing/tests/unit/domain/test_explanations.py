from pathlib import Path

import pytest

from processing.domain.explanations import (
    ECB_AAA_SPOT_EXPLANATIONS,
    ECB_ALL_SPOT_EXPLANATIONS,
    Explanations,
)

# tests/unit/domain/ -> the repository root is six levels up from this file.
NOTE = (
    Path(__file__).resolve().parents[6]
    / "docs/project/02-data-processing/01-plausibility-thresholds.md"
)

ECB_TEXTS = (
    "Outside the plausible range of \N{MINUS SIGN}2.00\N{NARROW NO-BREAK SPACE}% to "
    "8.00\N{NARROW NO-BREAK SPACE}%. ECB AAA spot yields stayed between "
    "\N{MINUS SIGN}1.00\N{NARROW NO-BREAK SPACE}% and 5.18\N{NARROW NO-BREAK SPACE}% since 2004.",
    "Moved more than 25 bp since the previous business day. "
    "This happened on 20 days since 2004, all in market stress.",
    "Moved more than 50 bp since the previous business day. "
    "This happened on only 2 days since 2004 (autumn 2008); check the source data.",
    "No value was published for this TARGET business day.",
    "No value for this maturity on a TARGET business day on which other maturities have one.",
)

ECB_ALL_TEXTS = (
    "Outside the plausible range of \N{MINUS SIGN}2.00\N{NARROW NO-BREAK SPACE}% to "
    "8.00\N{NARROW NO-BREAK SPACE}%. ECB all-issuer spot yields stayed between "
    "\N{MINUS SIGN}0.83\N{NARROW NO-BREAK SPACE}% and 5.84\N{NARROW NO-BREAK SPACE}% since 2004.",
    "Moved more than 25 bp since the previous business day. "
    "This happened on 51 days since 2004, mostly in market stress.",
    "Moved more than 50 bp since the previous business day. "
    "This happened on only 3 days since 2004 (2008 to 2010); check the source data.",
    "No value was published for this TARGET business day.",
    "No value for this maturity on a TARGET business day on which other maturities have one.",
)


@pytest.mark.parametrize("e", [ECB_AAA_SPOT_EXPLANATIONS, ECB_ALL_SPOT_EXPLANATIONS])
def test_every_explanation_appears_word_for_word_in_how_users_see_it(e: Explanations) -> None:
    text = NOTE.read_text(encoding="utf-8")
    section = text.split("## How users see it", 1)[1].split("\n## ", 1)[0]

    for explanation in (e.range_warn, e.jump_info, e.jump_warn, e.missing_date, e.missing_maturity):
        assert explanation in section


def test_the_ecb_texts_are_unchanged() -> None:
    e = ECB_AAA_SPOT_EXPLANATIONS
    assert (e.range_warn, e.jump_info, e.jump_warn, e.missing_date, e.missing_maturity) == ECB_TEXTS


def test_the_all_issuer_texts_are_unchanged() -> None:
    e = ECB_ALL_SPOT_EXPLANATIONS
    texts = (e.range_warn, e.jump_info, e.jump_warn, e.missing_date, e.missing_maturity)
    assert texts == ECB_ALL_TEXTS
