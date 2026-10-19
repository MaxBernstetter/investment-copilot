from datetime import timedelta

import pytest

from persistence.application.knowledge_time import resolve_as_of
from persistence.domain.curve import FutureAsOfError
from tests.unit.fakes import KNOWN_FROM, NOW, FakeCurveReader

pytestmark = pytest.mark.anyio


async def test_without_as_of_is_the_horizon() -> None:
    assert await resolve_as_of(FakeCurveReader(horizon=KNOWN_FROM), None) == KNOWN_FROM


async def test_an_as_of_before_the_horizon_is_kept() -> None:
    reader = FakeCurveReader(horizon=NOW)

    assert await resolve_as_of(reader, KNOWN_FROM) == KNOWN_FROM


async def test_an_as_of_after_the_horizon_is_capped_at_the_horizon() -> None:
    reader = FakeCurveReader(horizon=KNOWN_FROM)

    assert await resolve_as_of(reader, NOW) == KNOWN_FROM


async def test_an_as_of_after_the_database_clock_is_rejected() -> None:
    reader = FakeCurveReader(now=NOW, horizon=NOW)

    with pytest.raises(FutureAsOfError, match="in the future"):
        await resolve_as_of(reader, NOW + timedelta(microseconds=1))


async def test_the_future_check_uses_the_database_clock_not_the_horizon() -> None:
    reader = FakeCurveReader(now=NOW, horizon=KNOWN_FROM)

    with pytest.raises(FutureAsOfError, match="in the future"):
        await resolve_as_of(reader, NOW + timedelta(seconds=1))
