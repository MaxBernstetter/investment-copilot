from datetime import date
from decimal import Decimal

import pytest

from processing.application.check_quality import UnknownCurveError
from processing.application.get_quality_days import GetQualityDays
from processing.application.get_value_quality import GetValueQuality
from processing.application.knowledge_time import resolve_as_of
from processing.domain.calendar import target_business_days
from processing.domain.quality import Rule, Severity, Status
from processing.domain.read import FutureAsOfError, InvalidRangeError, rule_outcomes
from tests.unit.fakes import AS_OF, FROM, TO, FakeQualityStore

pytestmark = pytest.mark.anyio


async def test_resolve_as_of_rejects_a_future_time() -> None:
    with pytest.raises(FutureAsOfError):
        await resolve_as_of(FakeQualityStore(), AS_OF.replace(hour=9))


async def test_every_business_day_is_listed_and_unchecked_without_a_run() -> None:
    store = FakeQualityStore()
    store.checked = []
    store.stored_findings = []
    valid_from = date(2026, 10, 6)
    valid_to = date(2026, 10, 8)
    result = await GetQualityDays(store)("ecb-aaa-spot", valid_from, valid_to, AS_OF)

    expected_days = target_business_days(valid_from, valid_to)
    assert [day.valid_date for day in result.days] == expected_days
    for day in result.days:
        assert day.status is Status.UNCHECKED
        assert day.run_id is None
        assert len(day.rules) == 4
        assert all(rule.outcome is Status.UNCHECKED for rule in day.rules)
        assert day.findings == ()


async def test_a_checked_day_lists_all_four_rules_with_their_outcome() -> None:
    store = FakeQualityStore()
    result = await GetQualityDays(store)("ecb-aaa-spot", FROM, TO, AS_OF)

    day = result.days[0]
    assert len(day.rules) == 4
    rules_by_name = {rule.rule: rule for rule in day.rules}
    assert rules_by_name[Rule.MISSING_DATE].outcome is Status.WARN
    assert rules_by_name[Rule.MISSING_DATE].finding_count == 1
    assert rules_by_name[Rule.RANGE].outcome is Status.PASSED
    assert rules_by_name[Rule.JUMP].outcome is Status.PASSED
    assert rules_by_name[Rule.MISSING_MATURITY].outcome is Status.PASSED


async def test_get_quality_days_rejects_an_inverted_range() -> None:
    with pytest.raises(InvalidRangeError):
        await GetQualityDays(FakeQualityStore())(
            "ecb-aaa-spot", date(2026, 10, 8), date(2026, 10, 6), AS_OF
        )


async def test_get_quality_days_rejects_an_unknown_curve() -> None:
    with pytest.raises(UnknownCurveError):
        await GetQualityDays(FakeQualityStore())("unknown-curve", FROM, TO, AS_OF)


async def test_get_value_quality_passes_the_maturity_filter() -> None:
    store = FakeQualityStore()
    await GetValueQuality(store)("ecb-aaa-spot", FROM, TO, AS_OF, maturity="30Y")

    assert store.maturity_filter == "30Y"


async def test_value_quality_attaches_the_flags_of_each_version() -> None:
    from processing.domain.quality import Finding

    store = FakeQualityStore()
    store.stored_findings = [
        Finding(
            Rule.RANGE,
            Severity.WARN,
            FROM,
            "10Y",
            1,
            Decimal("2.5"),
            "Out of range",
            "2.5% is outside the band",
        )
    ]
    result = await GetValueQuality(store)("ecb-aaa-spot", FROM, TO, AS_OF)

    assert len(result.values) == 1
    value = result.values[0]
    assert value.version_id == 1
    assert value.flags == tuple(store.stored_findings)


async def test_meta_as_of_is_the_requested_as_of_or_the_database_time() -> None:
    store = FakeQualityStore()
    default = await GetQualityDays(store)("ecb-aaa-spot", FROM, TO, None)
    assert default.as_of == AS_OF

    explicit = await GetQualityDays(store)(
        "ecb-aaa-spot", FROM, TO, AS_OF.replace(hour=7, minute=30)
    )
    assert explicit.as_of == AS_OF.replace(hour=7, minute=30)


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
