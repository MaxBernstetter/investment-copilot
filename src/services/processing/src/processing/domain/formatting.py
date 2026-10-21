"""Number formats of evidence texts, following the design guidelines (D2).

Yields have three decimals, a true minus sign (U+2212) and a narrow no-break space (U+202F)
before the percent sign. Changes in basis points have one decimal, a thousands separator and
the same true minus sign. The characters are written as escapes because ruff flags them in text.
"""

from decimal import Decimal

NARROW_NO_BREAK_SPACE = "\N{NARROW NO-BREAK SPACE}"
MINUS_SIGN = "\N{MINUS SIGN}"


def format_yield(value: Decimal | float) -> str:
    """A yield in percent with three decimals, e.g. 2.871 % or a negative yield with U+2212."""
    rounded = round(float(value), 3)
    sign = MINUS_SIGN if rounded < 0 else ""
    return f"{sign}{abs(rounded):.3f}{NARROW_NO_BREAK_SPACE}%"


def format_bp(delta: float) -> str:
    """A change in basis points, signed with one decimal, e.g. +2,376.0 bp or a minus for -27.0."""
    rounded = round(delta, 1)
    if rounded == 0:
        return "0.0 bp"
    sign = "+" if rounded > 0 else MINUS_SIGN
    return f"{sign}{abs(rounded):,.1f} bp"
