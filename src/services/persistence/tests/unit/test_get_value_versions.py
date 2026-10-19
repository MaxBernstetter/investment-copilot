from datetime import date, timedelta

import pytest

from persistence.application.get_value_versions import GetValueVersions
from persistence.domain.curve import FutureAsOfError, NothingKnownError
from persistence.domain.observation import ChangeReason
from persistence.domain.versions import ValueVersion
from tests.unit.fakes import KNOWN_FROM, NOW, FakeCurveReader

pytestmark = pytest.mark.anyio

CURVE = "ecb-aaa-spot"
VALID_DATE = date(2026, 3, 12)


def version(
    version_id: int,
    value: float,
    known_from: timedelta,
    known_to: timedelta | None = None,
    change_reason: ChangeReason = ChangeReason.INITIAL,
) -> ValueVersion:
    return ValueVersion(
        version_id=version_id,
        value=value,
        known_from=KNOWN_FROM + known_from,
        known_to=None if known_to is None else KNOWN_FROM + known_to,
        source_id="ecb",
        run_id="ingestion-ecb-2026-03-12",
        change_reason=change_reason,
        normalization_version="1",
        delivery_id="delivery-1",
    )


def reader_with(*versions: ValueVersion, maturity: str = "10Y") -> FakeCurveReader:
    return FakeCurveReader(versions={(CURVE, maturity, VALID_DATE): list(versions)})


async def test_defaults_as_of_to_the_knowledge_horizon() -> None:
    reader = reader_with(version(1, 2.61, timedelta()))
    reader.horizon = NOW - timedelta(minutes=5)

    result = await GetValueVersions(reader)(CURVE, "10Y", VALID_DATE, None)

    assert result.as_of == reader.horizon


async def test_answers_an_as_of_after_the_horizon_at_the_horizon() -> None:
    reader = reader_with(version(1, 2.61, timedelta()))
    reader.horizon = NOW - timedelta(minutes=5)

    result = await GetValueVersions(reader)(CURVE, "10Y", VALID_DATE, NOW)

    assert result.as_of == reader.horizon


async def test_rejects_a_future_as_of() -> None:
    with pytest.raises(FutureAsOfError, match="in the future"):
        await GetValueVersions(reader_with(version(1, 2.61, timedelta())))(
            CURVE, "10Y", VALID_DATE, NOW + timedelta(seconds=1)
        )


async def test_off_grid_maturity_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="not on the grid"):
        await GetValueVersions(reader_with(version(1, 2.61, timedelta())))(
            CURVE, "4Y", VALID_DATE, None
        )


async def test_nothing_known_is_not_found() -> None:
    with pytest.raises(NothingKnownError, match="No published value"):
        await GetValueVersions(reader_with(version(1, 2.61, timedelta())))(
            CURVE, "10Y", VALID_DATE, KNOWN_FROM - timedelta(hours=1)
        )


async def test_returns_versions_oldest_first() -> None:
    reader = reader_with(
        version(2, 2.70, timedelta(hours=1), change_reason=ChangeReason.CORRECTION),
        version(1, 2.61, timedelta(), known_to=timedelta(hours=1)),
    )

    result = await GetValueVersions(reader)(CURVE, "10Y", VALID_DATE, None)

    assert result.curve_id == CURVE
    assert result.maturity == "10Y"
    assert result.valid_date == VALID_DATE
    assert [(v.version_id, v.value) for v in result.versions] == [(1, 2.61), (2, 2.70)]
    assert result.versions[0].known_to == KNOWN_FROM + timedelta(hours=1)
    assert result.versions[1].known_to is None
