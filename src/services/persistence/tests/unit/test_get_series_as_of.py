from datetime import date, timedelta

import pytest

from persistence.application.get_series_as_of import GetSeriesAsOf
from persistence.domain.curve import FutureAsOfError, NothingKnownError
from persistence.domain.series import InvalidRangeError
from tests.unit.fakes import KNOWN_FROM, NOW, FakeCurveReader

pytestmark = pytest.mark.anyio

CURVE = "ecb-aaa-spot"


def reader_with(values: dict[date, float], maturity: str = "10Y") -> FakeCurveReader:
    return FakeCurveReader(
        values={(CURVE, valid_date): {maturity: value} for valid_date, value in values.items()}
    )


async def test_defaults_as_of_to_the_knowledge_horizon() -> None:
    reader = FakeCurveReader(horizon=KNOWN_FROM, values={(CURVE, date(2026, 3, 12)): {"10Y": 2.61}})

    series = await GetSeriesAsOf(reader)(CURVE, "10Y", None, None, None)

    assert series.as_of == KNOWN_FROM


async def test_answers_an_as_of_after_the_horizon_at_the_horizon() -> None:
    reader = FakeCurveReader(horizon=KNOWN_FROM, values={(CURVE, date(2026, 3, 12)): {"10Y": 2.61}})

    series = await GetSeriesAsOf(reader)(CURVE, "10Y", None, None, NOW)

    assert series.as_of == KNOWN_FROM


async def test_keeps_an_as_of_at_or_before_the_horizon() -> None:
    reader = FakeCurveReader(horizon=NOW, values={(CURVE, date(2026, 3, 12)): {"10Y": 2.61}})

    earlier = await GetSeriesAsOf(reader)(CURVE, "10Y", None, None, KNOWN_FROM)
    at_horizon = await GetSeriesAsOf(reader)(CURVE, "10Y", None, None, NOW)

    assert earlier.as_of == KNOWN_FROM
    assert at_horizon.as_of == NOW


async def test_defaults_to_the_latest_known_date_and_the_year_before_it() -> None:
    reader = reader_with(
        {
            date(2025, 3, 11): 2.50,
            date(2025, 3, 13): 2.55,
            date(2026, 3, 13): 2.70,
        }
    )

    series = await GetSeriesAsOf(reader)(CURVE, "10Y", None, None, None)

    assert [(point.valid_date, point.value) for point in series.points] == [
        (date(2025, 3, 13), 2.55),
        (date(2026, 3, 13), 2.70),
    ]


async def test_rejects_an_as_of_in_the_future() -> None:
    with pytest.raises(FutureAsOfError, match="in the future"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            CURVE, "10Y", None, None, NOW + timedelta(seconds=1)
        )


async def test_rejects_a_range_that_is_reversed() -> None:
    with pytest.raises(InvalidRangeError, match="after to"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            CURVE, "10Y", date(2026, 3, 13), date(2026, 3, 12), None
        )


async def test_rejects_a_range_longer_than_the_maximum() -> None:
    with pytest.raises(InvalidRangeError, match="exceeds"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            CURVE, "10Y", date(2026, 3, 12) - timedelta(days=3661), date(2026, 3, 12), None
        )


async def test_accepts_a_range_of_exactly_the_maximum() -> None:
    series = await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
        CURVE, "10Y", date(2026, 3, 12) - timedelta(days=3660), date(2026, 3, 12), None
    )

    assert [point.valid_date for point in series.points] == [date(2026, 3, 12)]


async def test_an_unknown_maturity_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="not on the grid"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(CURVE, "4Y", None, None, None)


async def test_an_unknown_curve_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="not on the grid"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            "unknown-curve", "10Y", None, None, None
        )


async def test_nothing_known_as_of_is_not_found() -> None:
    before_knowledge = KNOWN_FROM - timedelta(hours=1)

    with pytest.raises(NothingKnownError, match="No published value"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            CURVE, "10Y", None, None, before_knowledge
        )


async def test_no_point_in_range_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="Nothing is known"):
        await GetSeriesAsOf(reader_with({date(2026, 3, 12): 2.61}))(
            CURVE, "10Y", date(2020, 1, 1), date(2020, 12, 31), None
        )


async def test_returns_the_known_points_in_date_order_and_skips_gaps() -> None:
    reader = reader_with({date(2026, 3, 14): 2.70, date(2026, 3, 12): 2.61})

    series = await GetSeriesAsOf(reader)(CURVE, "10Y", date(2026, 3, 11), date(2026, 3, 14), None)

    assert series.curve_id == CURVE
    assert series.maturity == "10Y"
    assert [point.valid_date for point in series.points] == [
        date(2026, 3, 12),
        date(2026, 3, 14),
    ]
