from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from persistence.domain.observation import (
    ChangeReason,
    Observation,
    OpenVersionExistsError,
    Origin,
)
from persistence.infrastructure.oracle import OracleObservationRepository, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase, stored_versions

pytestmark = pytest.mark.anyio

OPEN = datetime(9999, 12, 31)


@pytest.fixture
async def repository(oracle: OracleDatabase) -> AsyncIterator[OracleObservationRepository]:
    pool = create_pool(
        dsn=oracle.dsn,
        user="core_app",
        password=APP_PASSWORD,
        min_size=1,
        max_size=2,
        acquire_timeout_ms=5_000,
    )
    try:
        yield OracleObservationRepository(pool, call_timeout_ms=30_000)
    finally:
        await pool.close()


def observation(curve_id: str, maturity: str = "10Y", value: str = "2.61") -> Observation:
    return Observation(
        curve_id=curve_id,
        maturity=maturity,
        valid_date=date(2026, 3, 12),
        value=Decimal(value),
        origin=Origin.PUBLISHED,
        method_version=None,
        source_id="ecb",
        run_id="ingestion-ecb-2026-03-12",
        change_reason=ChangeReason.INITIAL,
    )


def database_clock(oracle: OracleDatabase) -> datetime:
    with oracle.connect_as_app() as connection, connection.cursor() as cursor:
        cursor.execute("select sys_extract_utc(systimestamp) from dual")
        (now,) = cursor.fetchone() or (None,)
        assert isinstance(now, datetime)
        return now.replace(tzinfo=UTC)


async def test_stores_every_value_with_valid_time_and_knowledge_time(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    before = database_clock(oracle)

    recorded = await repository.record_versions(
        [observation(curve_id, "2Y", "2.10"), observation(curve_id, "10Y", "2.61")]
    )

    after = database_clock(oracle)
    assert recorded.recorded_count == 2
    assert before <= recorded.known_from <= after
    versions = stored_versions(oracle, curve_id)
    assert [(v["maturity"], v["valid_date"], v["value"]) for v in versions] == [
        ("10Y", datetime(2026, 3, 12), 2.61),
        ("2Y", datetime(2026, 3, 12), 2.1),
    ]
    assert {v["known_from"].replace(tzinfo=UTC) for v in versions} == {recorded.known_from}
    assert {v["known_to"] for v in versions} == {OPEN}


async def test_stores_provenance_and_origin(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    derived = replace(
        observation(curve_id),
        origin=Origin.DERIVED,
        method_version="nss-1",
        source_id=None,
        change_reason=ChangeReason.RECALCULATION,
    )

    await repository.record_versions([derived])

    (version,) = stored_versions(oracle, curve_id)
    assert (
        version["origin"],
        version["method_version"],
        version["source_id"],
        version["run_id"],
        version["change_reason"],
    ) == ("derived", "nss-1", None, "ingestion-ecb-2026-03-12", "recalculation")


async def test_rejects_a_second_open_version_and_stores_nothing_of_the_batch(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    await repository.record_versions([observation(curve_id, "10Y")])

    with pytest.raises(OpenVersionExistsError):
        await repository.record_versions(
            [observation(curve_id, "2Y"), observation(curve_id, "10Y", "2.70")]
        )

    assert [v["maturity"] for v in stored_versions(oracle, curve_id)] == ["10Y"]


async def test_the_database_is_reachable(repository: OracleObservationRepository) -> None:
    assert await repository.is_reachable()
