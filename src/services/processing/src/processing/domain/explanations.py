"""Explanations shown per flag. The ECB texts match "How users see it" in the methodology note."""

from dataclasses import dataclass, replace

# docs/project/02-data-processing/01-plausibility-thresholds.md
# The minus is the Unicode MINUS SIGN and the space before % is a NARROW NO-BREAK SPACE (U+202F),
# as in the note. The escapes keep these characters visible in the source.
_MINUS = "\N{MINUS SIGN}"
_PCT = "\N{NARROW NO-BREAK SPACE}%"


@dataclass(frozen=True, slots=True)
class Explanations:
    """The texts shown per flag of one curve."""

    range_warn: str
    jump_info: str
    jump_warn: str
    missing_date: str
    missing_maturity: str


ECB_AAA_SPOT_EXPLANATIONS = Explanations(
    range_warn=(
        f"Outside the plausible range of {_MINUS}2.00{_PCT} to 8.00{_PCT}. "
        f"ECB AAA spot yields stayed between {_MINUS}1.00{_PCT} and 5.18{_PCT} since 2004."
    ),
    jump_info=(
        "Moved more than 25 bp since the previous business day. "
        "This happened on 20 days since 2004, all in market stress."
    ),
    jump_warn=(
        "Moved more than 50 bp since the previous business day. "
        "This happened on only 2 days since 2004 (autumn 2008); check the source data."
    ),
    missing_date="No value was published for this TARGET business day.",
    missing_maturity=(
        "No value for this maturity on a TARGET business day on which other maturities have one."
    ),
)

ECB_ALL_SPOT_EXPLANATIONS = replace(
    ECB_AAA_SPOT_EXPLANATIONS,
    range_warn=(
        f"Outside the plausible range of {_MINUS}2.00{_PCT} to 8.00{_PCT}. "
        f"ECB all-issuer spot yields stayed between {_MINUS}0.83{_PCT} and 5.84{_PCT} since 2004."
    ),
    jump_info=(
        "Moved more than 25 bp since the previous business day. "
        "This happened on 51 days since 2004, mostly in market stress."
    ),
    jump_warn=(
        "Moved more than 50 bp since the previous business day. "
        "This happened on only 3 days since 2004 (2008 to 2010); check the source data."
    ),
)
