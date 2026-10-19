from datetime import UTC, date, datetime, timedelta

import pytest

from persistence.application.get_curve_as_of import GetCurveAsOf
from persistence.domain.curve import FutureAsOfError, NothingKnownError
from tests.unit.fakes import KNOWN_FROM, NOW, FakeCurveReader

pytestmark = pytest.mark.anyio

CURVE = "ecb-aaa-spot"
VALID_DATE = date(2026, 3, 12)


def reader_with(**values: float) -> FakeCurveReader:
    return FakeCurveReader(values={(CURVE, VALID_DATE): values})


async def test_defaults_as_of_to_the_database_clock() -> None:
    curve = await GetCurveAsOf(reader_with(**{"10Y": 2.61}))(CURVE, VALID_DATE, None)

    assert curve.as_of == NOW


async def test_rejects_an_as_of_in_the_future() -> None:
    with pytest.raises(FutureAsOfError, match="in the future"):
        await GetCurveAsOf(reader_with())(CURVE, VALID_DATE, NOW + timedelta(seconds=1))


async def test_defaults_valid_date_to_the_latest_known() -> None:
    reader = FakeCurveReader(
        values={
            (CURVE, date(2026, 3, 12)): {"10Y": 2.61},
            (CURVE, date(2026, 3, 13)): {"10Y": 2.70},
        }
    )

    curve = await GetCurveAsOf(reader)(CURVE, None, None)

    assert curve.valid_date == date(2026, 3, 13)


async def test_nothing_known_at_as_of_is_not_found() -> None:
    before_knowledge = KNOWN_FROM - timedelta(hours=1)

    with pytest.raises(NothingKnownError, match="No published value"):
        await GetCurveAsOf(reader_with(**{"10Y": 2.61}))(CURVE, None, before_knowledge)


async def test_an_unknown_curve_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="Nothing is known"):
        await GetCurveAsOf(reader_with(**{"10Y": 2.61}))("unknown-curve", VALID_DATE, None)


async def test_all_points_missing_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="Nothing is known"):
        await GetCurveAsOf(reader_with())(CURVE, VALID_DATE, None)


async def test_keeps_missing_points_as_none() -> None:
    curve = await GetCurveAsOf(reader_with(**{"10Y": 2.61}))(CURVE, VALID_DATE, None)

    assert len(curve.points) == 11
    assert [point.maturity for point in curve.points][:3] == ["3M", "6M", "1Y"]
    assert curve.points[7].maturity == "10Y"
    assert curve.points[7].value == 2.61
    assert all(point.value is None for point in curve.points if point.maturity != "10Y")
    assert curve.as_of == datetime(2026, 3, 13, 9, 0, tzinfo=UTC)
