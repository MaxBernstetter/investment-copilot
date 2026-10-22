import pytest

from access.application.catalogue import CachedCatalogue
from access.domain.catalogue import CurveDefinition, GridMaturity
from access.domain.curve import CurveNotFoundError, PersistenceUnavailableError

pytestmark = pytest.mark.anyio


def curve(curve_id: str, attribution: str) -> CurveDefinition:
    return CurveDefinition(
        curve_id=curve_id,
        label="ECB euro area AAA spot",
        source_id="ecb",
        area="Euro area",
        attribution=attribution,
        rate_type="spot",
        compounding="continuous",
        unit="percent",
        source_model="Svensson",
        simulated=False,
        maturities=(GridMaturity(maturity="3M", months=3),),
    )


class FakeReader:
    def __init__(self, answer: tuple[CurveDefinition, ...]) -> None:
        self.answer = answer
        self.calls = 0
        self.error: Exception | None = None

    async def curves(self) -> tuple[CurveDefinition, ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.answer


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_reads_the_catalogue_once_within_the_ttl() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    clock = FakeClock()
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=clock)

    await catalogue.curves()
    clock.now = 59
    await catalogue.curves()

    assert reader.calls == 1


async def test_rereads_the_catalogue_after_the_ttl() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    clock = FakeClock()
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=clock)
    await catalogue.curves()

    newer = (curve("ecb-aaa-spot-sim", "Simulated scenario"),)
    reader.answer = newer
    clock.now = 60
    result = await catalogue.curves()

    assert reader.calls == 2
    assert result == newer


async def test_a_failed_read_is_not_cached() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    reader.error = PersistenceUnavailableError()
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=FakeClock())

    with pytest.raises(PersistenceUnavailableError):
        await catalogue.curves()

    reader.error = None
    result = await catalogue.curves()

    assert result == reader.answer
    assert reader.calls == 2


async def test_serves_the_last_loaded_catalogue_when_a_refresh_fails() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    clock = FakeClock()
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=clock)
    loaded = await catalogue.curves()

    reader.error = PersistenceUnavailableError()
    clock.now = 60
    result = await catalogue.curves()

    assert result == loaded
    assert reader.calls == 2

    reader.error = None
    clock.now = 120
    assert await catalogue.curves() == reader.answer
    assert reader.calls == 3


async def test_attribution_of_a_known_curve() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=FakeClock())

    assert await catalogue.attribution("ecb-aaa-spot") == "Source: ECB statistics"


async def test_an_unknown_curve_is_not_found() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=FakeClock())

    with pytest.raises(CurveNotFoundError) as error:
        await catalogue.attribution("unknown")

    assert error.value.detail == "no curve named unknown"


async def test_a_failed_refresh_is_retried_once_per_ttl() -> None:
    reader = FakeReader((curve("ecb-aaa-spot", "Source: ECB statistics"),))
    clock = FakeClock()
    catalogue = CachedCatalogue(reader, ttl_seconds=60, clock=clock)
    loaded = await catalogue.curves()

    reader.error = PersistenceUnavailableError()
    clock.now = 60
    assert await catalogue.curves() == loaded
    clock.now = 61
    assert await catalogue.curves() == loaded
    assert reader.calls == 2
