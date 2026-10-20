"""Explanations shown per flag. They match "How users see it" in the methodology note."""

# docs/project/02-data-processing/01-plausibility-thresholds.md
# The minus is the Unicode MINUS SIGN, as in the note.
_MINUS = "\N{MINUS SIGN}"

RANGE_WARN = (
    f"Outside the plausible range of {_MINUS}2.00 % to 8.00 %. "
    f"ECB AAA spot yields stayed between {_MINUS}1.00 % and 5.18 % since 2004."
)
JUMP_INFO = (
    "Moved more than 25 bp since the previous business day. "
    "This happened on 20 days since 2004, all in market stress."
)
JUMP_WARN = (
    "Moved more than 50 bp since the previous business day. "
    "This happened on only 2 days since 2004 (autumn 2008); check the source data."
)
