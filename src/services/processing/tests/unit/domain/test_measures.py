from datetime import date
from decimal import Decimal

import pytest

from processing.domain.measures import (
    MeasureInput,
    MeasureQuality,
    measure_point,
    worst_input_status,
)
from processing.domain.quality import Status

D = date(2026, 10, 8)


def _inputs(
    values: dict[str, str], statuses: dict[str, Status] | None = None
) -> dict[str, MeasureInput]:
    statuses = statuses or {}
    return {
        maturity: MeasureInput(
            maturity=maturity,
            value=Decimal(value),
            version_id=index + 1,
            status=statuses.get(maturity, Status.PASSED),
        )
        for index, (maturity, value) in enumerate(values.items())
    }


def test_spread_2y_10y_is_10y_minus_2y_in_basis_points() -> None:
    point = measure_point(D, _inputs({"2Y": "1.95", "10Y": "2.61"}))

    assert point.spread_2y_10y == Decimal("66.00")
    assert point.inverted is False


def test_spread_3m_10y_is_10y_minus_3m_in_basis_points() -> None:
    point = measure_point(D, _inputs({"3M": "1.90", "10Y": "2.61"}))

    assert point.spread_3m_10y == Decimal("71.00")


def test_curvature_is_twice_5y_minus_2y_and_10y_in_basis_points() -> None:
    point = measure_point(D, _inputs({"2Y": "1.95", "5Y": "2.18", "10Y": "2.61"}))

    assert point.curvature_2y_5y_10y == Decimal("-20.00")


def test_a_negative_spread_is_inverted() -> None:
    point = measure_point(D, _inputs({"2Y": "3.10", "10Y": "2.85"}))

    assert point.spread_2y_10y == Decimal("-25.00")
    assert point.inverted is True


def test_a_spread_of_exactly_zero_is_not_inverted() -> None:
    point = measure_point(D, _inputs({"2Y": "2.50", "10Y": "2.50"}))

    assert point.spread_2y_10y == Decimal("0.00")
    assert point.inverted is False


def test_measures_are_not_rounded() -> None:
    point = measure_point(D, _inputs({"2Y": "1.955", "10Y": "2.6125"}))

    assert point.spread_2y_10y == Decimal("65.7500")


def test_a_missing_5y_nulls_only_the_curvature() -> None:
    point = measure_point(D, _inputs({"3M": "1.90", "2Y": "1.95", "10Y": "2.61"}))

    assert point.curvature_2y_5y_10y is None
    assert point.spread_2y_10y == Decimal("66.00")
    assert point.spread_3m_10y == Decimal("71.00")
    assert point.missing == ("5Y",)


def test_a_missing_10y_nulls_every_measure_and_the_inversion() -> None:
    point = measure_point(D, _inputs({"3M": "1.90", "2Y": "1.95", "5Y": "2.18"}))

    assert point.spread_2y_10y is None
    assert point.spread_3m_10y is None
    assert point.curvature_2y_5y_10y is None
    assert point.inverted is None
    assert point.missing == ("10Y",)


def test_a_warn_on_10y_makes_the_point_warn_and_flags_10y() -> None:
    point = measure_point(
        D,
        _inputs(
            {"3M": "1.90", "2Y": "1.95", "5Y": "2.18", "10Y": "2.61"},
            {"10Y": Status.WARN},
        ),
    )

    assert point.quality == MeasureQuality(Status.WARN, ("10Y",))
    assert point.spread_2y_10y == Decimal("66.00")


def test_an_info_input_is_flagged() -> None:
    point = measure_point(D, _inputs({"2Y": "1.95", "10Y": "2.61"}, {"2Y": Status.INFO}))

    assert point.quality == MeasureQuality(Status.INFO, ("2Y",))


def test_an_unchecked_input_is_not_flagged() -> None:
    point = measure_point(D, _inputs({"5Y": "2.18"}, {"5Y": Status.UNCHECKED}))

    assert point.quality == MeasureQuality(Status.UNCHECKED, ())


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([Status.PASSED, Status.UNCHECKED], Status.UNCHECKED),
        ([Status.UNCHECKED, Status.INFO], Status.INFO),
        ([Status.INFO, Status.WARN, Status.PASSED], Status.WARN),
        ([], Status.PASSED),
    ],
)
def test_worst_input_status_orders_warn_info_unchecked_passed(
    statuses: list[Status], expected: Status
) -> None:
    assert worst_input_status(statuses) == expected


def test_inputs_and_missing_follow_the_input_order() -> None:
    point = measure_point(D, _inputs({"10Y": "2.61", "3M": "1.90"}))

    assert [i.maturity for i in point.inputs] == ["3M", "10Y"]
    assert point.missing == ("2Y", "5Y")
