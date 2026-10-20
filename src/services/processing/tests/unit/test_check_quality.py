from datetime import UTC, date, datetime, timedelta

import pytest

from processing.application.check_quality import CheckQuality, FindingCount, UnknownCurveError
from processing.application.ports import Grid, ObservationReader, QualityStore
from processing.domain.assessment import QualityCheck
from processing.domain.quality import Rule, Severity, Status, Value

pytestmark = pytest.mark.anyio

CHECKED_AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
GRID = ("10Y", "30Y")


SeriesCall = tuple[str, date, date, datetime]


class FakeReader(ObservationReader):
    def __init__(
        self,
        grid: Grid | None,
        series_calls: list[SeriesCall],
        *,
        fail: bool = False,
    ) -> None:
        self._grid = grid
        self.series_calls = series_calls
        self._fail = fail

    async def grid(self, curve_id: str) -> Grid | None:
        if self._fail:
            raise AssertionError("grid should not be called")
        assert curve_id == "ecb-aaa-spot-sim"
        return self._grid

    async def series(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
    ) -> list[Value]:
        if self._fail:
            raise AssertionError("series should not be called")
        self.series_calls.append((maturity, valid_from, valid_to, as_of))
        return []


class RecordingStore(QualityStore):
    def __init__(self) -> None:
        self.checks: list[QualityCheck] = []

    async def record(self, check: QualityCheck) -> None:
        self.checks.append(check)


async def test_a_range_longer_than_a_year_is_checked_in_chunks_at_one_knowledge_time() -> None:
    valid_from = date(2025, 1, 1)
    valid_to = date(2026, 1, 2)
    series_calls: list[SeriesCall] = []
    reader = FakeReader(Grid(maturities=GRID, as_of=CHECKED_AS_OF), series_calls)
    store = RecordingStore()
    use_case = CheckQuality(reader, store)

    summary = await use_case("ecb-aaa-spot-sim", valid_from, valid_to, "run-1")

    assert summary.chunks == 2
    assert summary.checked_as_of == CHECKED_AS_OF
    assert summary.worst_status is Status.WARN
    assert summary.finding_counts == (
        FindingCount(rule=Rule.MISSING_DATE, severity=Severity.WARN, count=256),
    )
    assert len(store.checks) == 2
    assert store.checks[0].valid_from == valid_from
    assert store.checks[0].valid_to == date(2026, 1, 1)
    assert store.checks[1].valid_from == date(2026, 1, 2)
    assert store.checks[1].valid_to == valid_to
    assert all(check.checked_as_of == CHECKED_AS_OF for check in store.checks)
    assert all(check.run_id == "run-1" for check in store.checks)

    first_chunk_end = date(2026, 1, 1)
    expected_lead_in = valid_from - timedelta(days=31)
    for maturity in GRID:
        assert (maturity, expected_lead_in, first_chunk_end, CHECKED_AS_OF) in series_calls
        assert (
            maturity,
            date(2026, 1, 2) - timedelta(days=31),
            date(2026, 1, 2),
            CHECKED_AS_OF,
        ) in series_calls


async def test_nothing_known_records_nothing() -> None:
    store = RecordingStore()
    use_case = CheckQuality(FakeReader(None, []), store)

    summary = await use_case("ecb-aaa-spot-sim", date(2026, 10, 5), date(2026, 10, 8), "run-1")

    assert summary.checked_as_of is None
    assert summary.chunks == 0
    assert store.checks == []


async def test_an_unknown_curve_fails_before_any_read() -> None:
    use_case = CheckQuality(FakeReader(None, [], fail=True), RecordingStore())

    with pytest.raises(UnknownCurveError):
        await use_case("unknown-curve", date(2026, 10, 5), date(2026, 10, 8), "run-1")
