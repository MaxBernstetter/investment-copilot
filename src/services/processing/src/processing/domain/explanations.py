"""Explanations shown per flag. They match "How users see it" in the methodology note."""

# docs/project/02-data-processing/01-plausibility-thresholds.md
# The minus is the Unicode MINUS SIGN and the space before % is a NARROW NO-BREAK SPACE (U+202F),
# as in the note. The escapes keep these characters visible in the source.
_MINUS = "\N{MINUS SIGN}"
_PCT = "\N{NARROW NO-BREAK SPACE}%"

RANGE_WARN = (
    f"Outside the plausible range of {_MINUS}2.00{_PCT} to 8.00{_PCT}. "
    f"ECB AAA spot yields stayed between {_MINUS}1.00{_PCT} and 5.18{_PCT} since 2004."
)
JUMP_INFO = (
    "Moved more than 25 bp since the previous business day. "
    "This happened on 20 days since 2004, all in market stress."
)
JUMP_WARN = (
    "Moved more than 50 bp since the previous business day. "
    "This happened on only 2 days since 2004 (autumn 2008); check the source data."
)

MISSING_DATE = "No value was published for this TARGET business day."
MISSING_MATURITY = (
    "No value for this maturity on a TARGET business day on which other maturities have one."
)
