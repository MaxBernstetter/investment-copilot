from datetime import date

import pytest

from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.application.knowledge_time import resolve_as_of
from processing.domain.assessment import CheckedDay
from processing.domain.quality import Rule, Severity, Status
from processing.domain.read import FutureAsOfError, InvalidRangeError, rule_outcomes
from tests.unit.fakes import AS_OF, FROM, TO, FakeQualityStore

pytestmark = pytest.mark.anyio


async def test_resolve_as_of_rejects_a_future_time() -> None:
    with pytest.raises(FutureAsOfError):
        await resolve_as_of(FakeQualityStore(), AS_OF.replace(hour=9))


async def test_get_quality_days_fills_unchecked_business_days() -> None:
    store = FakeQualityStore()
    store.checked = [
        CheckedDay(date(2026, 10, 6), Status.PASSED, "run-1", AS_OF),
        CheckedDay(FROM, Status.WARN, "run-1", AS_OF),
    ]
    end = date(2026, 10, 8)
    result = await GetQualityDays(store)("ecb-aaa-spot", date(2026, 10, 6), end, AS_OF)

    assert [day.status for day in result.days] == [Status.PASSED, Status.WARN, Status.UNCHECKED]


async def test_get_quality_days_rejects_an_inverted_range() -> None:
    with pytest.raises(InvalidRangeError):
        await GetQualityDays(FakeQualityStore())(
            "ecb-aaa-spot", date(2026, 10, 8), date(2026, 10, 6), AS_OF
        )


async def test_get_value_quality_passes_the_maturity_filter() -> None:
    store = FakeQualityStore()
    await GetValueQuality(store)("ecb-aaa-spot", FROM, TO, AS_OF, maturity="30Y")

    assert store.maturity_filter == "30Y"


def test_rule_outcomes_use_the_worst_finding_per_rule() -> None:
    from processing.domain.quality import Finding

    finding = Finding(
        Rule.RANGE,
        Severity.WARN,
        FROM,
        "10Y",
        1,
        None,
        "",
        "",
    )
    outcomes = rule_outcomes((finding,), checked=True)

    assert outcomes[0].outcome is Status.WARN
