from decimal import Decimal

from processing.domain.formatting import format_bp, format_yield

NNBSP = "\N{NARROW NO-BREAK SPACE}"
MINUS = "\N{MINUS SIGN}"


def test_a_yield_has_three_decimals_and_a_narrow_no_break_space_before_the_percent() -> None:
    assert format_yield(2.87) == f"2.870{NNBSP}%"
    assert format_yield(Decimal("2.871")) == f"2.871{NNBSP}%"


def test_a_negative_yield_uses_the_true_minus_sign() -> None:
    assert format_yield(-2.01) == f"{MINUS}2.010{NNBSP}%"


def test_a_positive_bp_move_is_signed_with_one_decimal() -> None:
    assert format_bp(30) == "+30.0 bp"
    assert format_bp(0.04) == "0.0 bp"


def test_a_negative_bp_move_uses_the_true_minus_sign() -> None:
    assert format_bp(-27) == f"{MINUS}27.0 bp"


def test_a_bp_move_of_1000_or_more_has_a_thousands_separator() -> None:
    assert format_bp(2376) == "+2,376.0 bp"
    assert format_bp(-2376.04) == f"{MINUS}2,376.0 bp"
