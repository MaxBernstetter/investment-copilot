"""The declared US Treasury schema (Pandera on Polars) against recorded and broken payloads."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import pytest

from ingestion.domain.observation import PublishedObservation
from ingestion.infrastructure.ust.payload import (
    CURVE_ID,
    NORMALIZATION_VERSION,
    InvalidPayloadError,
    parse_payload,
)
from tests.recorded import (
    UST_EMPTY_2027,
    UST_MALFORMED_2025,
    UST_MISSING_COLUMN_2025,
    UST_NEW_COLUMN_2025,
    UST_YEAR_1990,
    UST_YEAR_2004,
    UST_YEAR_2025,
    ust_payload,
)

DEC_31_2025 = date(2025, 12, 31)
FEB_18_2025 = date(2025, 2, 18)
JAN_2_2025 = date(2025, 1, 2)


def maturities(observations: Iterable[PublishedObservation]) -> set[str]:
    return {observation.maturity for observation in observations}


def test_a_year_before_20y_and_30y_maps_its_nine_columns() -> None:
    observations, unknown = parse_payload(ust_payload(UST_YEAR_1990))

    assert len(observations) == 5 * 9
    assert maturities(observations) == {"3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"}
    assert unknown == ()


def test_a_year_without_30y_maps_its_columns_and_no_30y() -> None:
    observations, unknown = parse_payload(ust_payload(UST_YEAR_2004))

    assert len(observations) == 5 * 10
    assert maturities(observations) == {
        "1M",
        "3M",
        "6M",
        "1Y",
        "2Y",
        "3Y",
        "5Y",
        "7Y",
        "10Y",
        "20Y",
    }
    assert unknown == ()


def test_an_empty_cell_is_no_observation_and_the_value_keeps_its_digits() -> None:
    observations, _ = parse_payload(ust_payload(UST_YEAR_2025))

    half_month = [o for o in observations if o.maturity == "1.5M"]
    assert [(o.valid_date, o.value) for o in half_month] == [
        (DEC_31_2025, Decimal("3.75")),
        (FEB_18_2025, Decimal("4.41")),
    ]
    assert not [o for o in observations if o.maturity == "1.5M" and o.valid_date == JAN_2_2025]
    assert len(observations) == 4 * 14 - 2


def test_a_row_maps_to_grid_tenors_with_the_curve_and_versions() -> None:
    observations, _ = parse_payload(ust_payload(UST_YEAR_2025))

    year_end = [o for o in observations if o.valid_date == DEC_31_2025]
    ten_year = next(o for o in year_end if o.maturity == "10Y")
    assert ten_year.value == Decimal("4.18")
    assert {o.curve_id for o in observations} == {CURVE_ID} == {"ust-par"}
    assert {o.normalization_version for o in observations} == {NORMALIZATION_VERSION}


def test_the_row_order_does_not_change_the_observations() -> None:
    lines = ust_payload(UST_YEAR_2025).decode().splitlines()
    reversed_rows = "\n".join([lines[0], *reversed(lines[1:])]).encode()

    forward, _ = parse_payload(ust_payload(UST_YEAR_2025))
    backward, _ = parse_payload(reversed_rows)

    assert sorted(forward, key=repr) == sorted(backward, key=repr)


def test_an_unknown_column_is_accepted_and_reported() -> None:
    observations, unknown = parse_payload(ust_payload(UST_NEW_COLUMN_2025))

    assert unknown == ("9 Mo",)
    assert "9M" not in maturities(observations)
    assert len(observations) == 4 * 14 - 2


def test_a_missing_required_column_fails_the_load() -> None:
    with pytest.raises(InvalidPayloadError):
        parse_payload(ust_payload(UST_MISSING_COLUMN_2025))


def test_a_malformed_date_or_value_fails_the_load() -> None:
    with pytest.raises(InvalidPayloadError):
        parse_payload(ust_payload(UST_MALFORMED_2025))


def test_an_empty_body_is_no_observation() -> None:
    assert parse_payload(ust_payload(UST_EMPTY_2027)) == ([], ())
    assert parse_payload(b"  \n") == ([], ())


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(
            "12/31/2025,3.74,3.75,3.67,3.67,3.63,3.59,3.48,3.47,3.55,3.73,3.94,4.18,4.79,4.84",
            id="duplicate date",
        ),
        pytest.param(
            "02/30/2025,3.74,3.75,3.67,3.67,3.63,3.59,3.48,3.47,3.55,3.73,3.94,4.18,4.79,4.84",
            id="not a calendar date",
        ),
    ],
)
def test_a_duplicate_or_impossible_date_fails_the_load(row: str) -> None:
    lines = ust_payload(UST_YEAR_2025).decode().splitlines()
    body = "\n".join([*lines, row]).encode()

    with pytest.raises(InvalidPayloadError):
        parse_payload(body)
