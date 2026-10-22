from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from processing.application.check_quality import UnknownCurveError
from processing.application.get_measures import GetMeasures
from processing.domain.assessment import ValueStatus
from processing.domain.measures import MAX_MEASURES_RANGE, MeasureInput, MeasureQuality
from processing.domain.quality import Status, Value
from processing.domain.read import FutureAsOfError, InvalidRangeError
from tests.unit.fakes import AS_OF, FakeMeasureQuality, FakeObservationReader

CURVE = "ecb-aaa-spot"
HORIZON = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
DAY = date(2026, 10, 8)
KNOWN = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
ALL_MATURITIES = ("3M", "2Y", "5Y", "10Y")


def _value(version_id: int, maturity: str, value: str, day: date = DAY) -> Value:
    return Value(version_id, maturity, day, Decimal(value))


def _scenario(*, unknown: bool = False) -> tuple[FakeObservationReader, FakeMeasureQuality]:
    observations = FakeObservationReader(
        horizon=HORIZON,
        versions=[
            (KNOWN, _value(1, "3M", "1.98")),
            (KNOWN, _value(2, "2Y", "1.98")),
            (KNOWN, _value(3, "5Y", "2.21")),
            (KNOWN, _value(4, "10Y", "2.64")),
        ],
        unknown=unknown,
    )
    return observations, FakeMeasureQuality()


def _use_case(observations: FakeObservationReader, quality: FakeMeasureQuality) -> GetMeasures:
    return GetMeasures(observations, quality)


@pytest.mark.anyio
async def test_without_as_of_the_inputs_are_read_at_the_persistence_horizon() -> None:
    observations, quality = _scenario()

    result = await _use_case(observations, quality)(CURVE, DAY, DAY, None)

    assert result.as_of == HORIZON
    assert {at for _, at in observations.series_calls} == {HORIZON}
    assert {at for _, at in quality.calls} == {HORIZON}
    assert {maturity for maturity, _ in quality.calls} == set(ALL_MATURITIES)


@pytest.mark.anyio
async def test_a_requested_as_of_before_the_horizon_is_echoed() -> None:
    observations, quality = _scenario()
    as_of = HORIZON - timedelta(hours=2)

    result = await _use_case(observations, quality)(CURVE, DAY, DAY, as_of)

    assert result.as_of == as_of
    assert {at for _, at in observations.series_calls} == {as_of}


@pytest.mark.anyio
async def test_an_as_of_after_the_horizon_is_answered_at_the_horizon() -> None:
    observations = FakeObservationReader(horizon=HORIZON - timedelta(hours=1))
    quality = FakeMeasureQuality(now=HORIZON)

    result = await _use_case(observations, quality)(CURVE, DAY, DAY, HORIZON)

    assert result.as_of == HORIZON - timedelta(hours=1)


@pytest.mark.anyio
async def test_a_future_as_of_is_rejected() -> None:
    observations, quality = _scenario()

    with pytest.raises(FutureAsOfError):
        await _use_case(observations, quality)(CURVE, DAY, DAY, AS_OF + timedelta(seconds=1))


@pytest.mark.anyio
async def test_a_curve_without_thresholds_is_unknown() -> None:
    observations, quality = _scenario()

    with pytest.raises(UnknownCurveError):
        await _use_case(observations, quality)("unknown-curve", DAY, DAY, None)


@pytest.mark.anyio
async def test_a_curve_unknown_to_persistence_is_unknown() -> None:
    observations, quality = _scenario(unknown=True)

    with pytest.raises(UnknownCurveError):
        await _use_case(observations, quality)(CURVE, DAY, DAY, None)


@pytest.mark.anyio
async def test_from_after_to_is_rejected() -> None:
    observations, quality = _scenario()

    with pytest.raises(InvalidRangeError):
        await _use_case(observations, quality)(CURVE, DAY, DAY - timedelta(days=1), None)


@pytest.mark.anyio
async def test_a_range_over_3660_days_is_rejected() -> None:
    observations, quality = _scenario()

    with pytest.raises(InvalidRangeError):
        await _use_case(observations, quality)(
            CURVE, DAY - MAX_MEASURES_RANGE - timedelta(days=1), DAY, None
        )


@pytest.mark.anyio
async def test_a_range_of_3660_days_is_accepted() -> None:
    observations, quality = _scenario()

    result = await _use_case(observations, quality)(CURVE, DAY - MAX_MEASURES_RANGE, DAY, None)

    assert result.points[0].valid_date == DAY


@pytest.mark.anyio
async def test_one_point_per_valid_date_with_a_known_input() -> None:
    observations = FakeObservationReader(
        horizon=HORIZON,
        versions=[
            (KNOWN, _value(1, "10Y", "2.64", DAY + timedelta(days=1))),
            (KNOWN, _value(2, "2Y", "1.98", DAY)),
            (KNOWN, _value(3, "3M", "1.98", DAY)),
            (KNOWN, _value(4, "5Y", "2.21", DAY)),
            (KNOWN, _value(5, "10Y", "2.64", DAY)),
            (KNOWN, _value(6, "3M", "1.90", DAY - timedelta(days=2))),
        ],
    )
    quality = FakeMeasureQuality()

    result = await _use_case(observations, quality)(
        CURVE, DAY - timedelta(days=2), DAY + timedelta(days=1), None
    )

    dates = [point.valid_date for point in result.points]
    assert dates == [DAY - timedelta(days=2), DAY, DAY + timedelta(days=1)]
    only_3m = result.points[0]
    assert [i.maturity for i in only_3m.inputs] == ["3M"]
    assert only_3m.missing == ("2Y", "5Y", "10Y")
    assert only_3m.spread_2y_10y is None


@pytest.mark.anyio
async def test_an_input_takes_the_status_of_its_own_version() -> None:
    observations, _ = _scenario()
    quality = FakeMeasureQuality(
        statuses=[ValueStatus(99, "10Y", DAY, Status.WARN)],
    )

    result = await _use_case(observations, quality)(CURVE, DAY, DAY, None)

    ten_year = next(i for i in result.points[0].inputs if i.maturity == "10Y")
    assert ten_year.status is Status.UNCHECKED
    assert result.points[0].quality.status is Status.UNCHECKED


@pytest.mark.anyio
async def test_a_correction_changes_the_measures_only_after_its_knowledge_time() -> None:
    t0 = datetime(2026, 10, 9, 7, 0, tzinfo=UTC)
    t1 = datetime(2026, 10, 9, 7, 30, tzinfo=UTC)
    observations = FakeObservationReader(
        horizon=HORIZON,
        versions=[
            (KNOWN, _value(2, "2Y", "1.98")),
            (KNOWN, _value(3, "3M", "1.98")),
            (KNOWN, _value(5, "5Y", "2.21")),
            (t0, _value(11, "10Y", "26.40")),
            (t1, _value(12, "10Y", "2.64")),
        ],
    )
    quality = FakeMeasureQuality(
        statuses=[
            ValueStatus(11, "10Y", DAY, Status.WARN),
            ValueStatus(12, "10Y", DAY, Status.PASSED),
            ValueStatus(2, "2Y", DAY, Status.PASSED),
            ValueStatus(3, "3M", DAY, Status.PASSED),
            ValueStatus(5, "5Y", DAY, Status.PASSED),
        ],
    )
    use_case = _use_case(observations, quality)

    before = await use_case(CURVE, DAY, DAY, t0 + timedelta(seconds=1))
    after = await use_case(CURVE, DAY, DAY, t1)

    point = before.points[0]
    assert point.spread_2y_10y == Decimal("2442.00")
    assert point.quality == MeasureQuality(Status.WARN, ("10Y",))
    assert next(i for i in point.inputs if i.maturity == "10Y").version_id == 11
    assert after.points[0].spread_2y_10y == Decimal("66.00")
    assert after.points[0].quality == MeasureQuality(Status.PASSED, ())
    assert next(i for i in after.points[0].inputs if i.maturity == "10Y") == MeasureInput(
        "10Y", Decimal("2.64"), 12, Status.PASSED
    )


@pytest.mark.anyio
async def test_meta_method_version_is_1() -> None:
    observations, quality = _scenario()

    result = await _use_case(observations, quality)(CURVE, DAY, DAY, None)

    assert result.method_version == "1"
