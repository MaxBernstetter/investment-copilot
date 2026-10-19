from datetime import date, timedelta

import pytest

from persistence.application.get_curve_changes import GetCurveChanges
from persistence.domain.changes import ValueChange
from persistence.domain.curve import FutureAsOfError, NothingKnownError
from persistence.domain.observation import ChangeReason
from persistence.domain.series import InvalidRangeError
from tests.unit.fakes import KNOWN_FROM, NOW, FakeCurveReader

pytestmark = pytest.mark.anyio

CURVE = "ecb-aaa-spot"
FROM = date(2026, 3, 1)
TO = date(2026, 3, 31)


def change(valid_date: date = date(2026, 3, 12), new_value: float = 2.7) -> ValueChange:
    return ValueChange(
        valid_date=valid_date,
        maturity="10Y",
        old_value=2.61,
        new_value=new_value,
        change_reason=ChangeReason.CORRECTION,
        source_id="ecb",
        known_from=KNOWN_FROM + timedelta(hours=1),
    )


def reader_with(*changes: ValueChange) -> FakeCurveReader:
    reader = FakeCurveReader(horizon=NOW - timedelta(minutes=5))
    reader.value_changes = {CURVE: list(changes)}
    return reader


async def test_returns_the_changes_and_echoes_both_times() -> None:
    reader = reader_with(change())
    since = KNOWN_FROM
    as_of = NOW - timedelta(minutes=10)

    result = await GetCurveChanges(reader)(CURVE, FROM, TO, since, as_of)

    assert result.curve_id == CURVE
    assert (result.valid_from, result.valid_to) == (FROM, TO)
    assert (result.since, result.as_of) == (since, as_of)
    assert result.changes == (change(),)


async def test_without_as_of_reads_at_the_horizon() -> None:
    reader = reader_with(change())

    result = await GetCurveChanges(reader)(CURVE, FROM, TO, KNOWN_FROM, None)

    assert result.as_of == reader.horizon
    assert reader.change_reads == [(KNOWN_FROM, reader.horizon)]


async def test_since_after_the_horizon_is_capped_at_the_horizon() -> None:
    reader = reader_with()

    result = await GetCurveChanges(reader)(CURVE, FROM, TO, NOW - timedelta(minutes=1), None)

    assert result.since == reader.horizon
    assert result.as_of == reader.horizon
    assert result.changes == ()


async def test_since_after_as_of_is_an_invalid_range() -> None:
    with pytest.raises(InvalidRangeError, match="is after as_of"):
        await GetCurveChanges(reader_with(change()))(
            CURVE, FROM, TO, KNOWN_FROM + timedelta(hours=2), KNOWN_FROM
        )


async def test_from_after_to_is_an_invalid_range() -> None:
    with pytest.raises(InvalidRangeError, match="is after to"):
        await GetCurveChanges(reader_with(change()))(CURVE, TO, FROM, KNOWN_FROM, None)


async def test_a_range_over_3660_days_is_invalid() -> None:
    with pytest.raises(InvalidRangeError, match="exceeds 3660 days"):
        await GetCurveChanges(reader_with(change()))(
            CURVE, date(2016, 1, 1), date(2026, 3, 31), KNOWN_FROM, None
        )


async def test_future_since_is_rejected() -> None:
    with pytest.raises(FutureAsOfError, match="in the future"):
        await GetCurveChanges(reader_with(change()))(
            CURVE, FROM, TO, NOW + timedelta(seconds=1), None
        )


async def test_undefined_curve_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="is not defined"):
        await GetCurveChanges(reader_with(change()))("unknown-curve", FROM, TO, KNOWN_FROM, None)


async def test_no_change_is_an_empty_list() -> None:
    result = await GetCurveChanges(reader_with())(CURVE, FROM, TO, KNOWN_FROM, None)

    assert result.changes == ()
