import pytest

from persistence.domain.observation import InvalidObservationsError, Origin, ensure_unique_keys
from tests.unit.fakes import published


def test_derived_observation_needs_a_method_version() -> None:
    with pytest.raises(InvalidObservationsError, match="method version"):
        published(origin=Origin.DERIVED)


def test_published_observation_has_no_method_version() -> None:
    with pytest.raises(InvalidObservationsError, match="method version"):
        published(method_version="nss-1")


def test_distinct_maturities_origins_and_method_versions_are_distinct_observations() -> None:
    ensure_unique_keys(
        [
            published(maturity="10Y"),
            published(maturity="2Y"),
            published(origin=Origin.DERIVED, method_version="nss-1", source_id=None),
            published(origin=Origin.DERIVED, method_version="nss-2", source_id=None),
        ]
    )


def test_an_observation_may_appear_only_once_per_batch() -> None:
    with pytest.raises(InvalidObservationsError, match=r"1 observation\(s\).*10Y 2026-03-12"):
        ensure_unique_keys([published(value="2.61"), published(value="2.70")])
