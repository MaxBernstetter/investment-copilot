import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import oracledb
import pytest

from persistence.domain.observation import (
    ChangeReason,
    InvalidObservationsError,
    Observation,
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


async def test_a_changed_value_closes_the_open_version_and_opens_a_new_one(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    first = await repository.record_versions([observation(curve_id, "10Y", "2.61")])

    second = await repository.record_versions([observation(curve_id, "10Y", "2.70")])

    assert (second.recorded_count, second.unchanged_count) == (1, 0)
    assert first.known_from < second.known_from
    assert [
        (v["value"], v["known_from"].replace(tzinfo=UTC), v["known_to"])
        for v in stored_versions(oracle, curve_id)
    ] == [
        (2.61, first.known_from, second.known_from.replace(tzinfo=None)),
        (2.7, second.known_from, OPEN),
    ]


async def test_an_unchanged_reload_is_an_idempotent_no_op(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    batch = [observation(curve_id, "2Y", "2.10"), observation(curve_id, "10Y", "2.61")]
    await repository.record_versions(batch)
    before = stored_versions(oracle, curve_id)
    reload = [replace(o, run_id="ingestion-ecb-2026-03-13") for o in batch]

    recorded = await repository.record_versions(reload)

    assert (recorded.recorded_count, recorded.unchanged_count) == (0, 2)
    assert stored_versions(oracle, curve_id) == before


async def test_rejects_a_batch_with_duplicates_and_stores_nothing_of_it(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    await repository.record_versions([observation(curve_id, "10Y")])

    with pytest.raises(InvalidObservationsError):
        await repository.record_versions(
            [
                observation(curve_id, "2Y"),
                observation(curve_id, "10Y", "2.70"),
                observation(curve_id, "10Y", "2.80"),
            ]
        )

    assert [(v["maturity"], v["known_to"]) for v in stored_versions(oracle, curve_id)] == [
        ("10Y", OPEN)
    ]


async def test_concurrent_writers_of_one_observation_are_serialized(
    oracle: OracleDatabase, repository: OracleObservationRepository, curve_id: str
) -> None:
    await repository.record_versions([observation(curve_id, "10Y", "2.61")])

    with oracle.connect_as_app() as first:
        record_without_commit(first, observation(curve_id, "10Y", "2.70"))
        second = asyncio.create_task(
            repository.record_versions([observation(curve_id, "10Y", "2.80")])
        )
        await asyncio.sleep(1)
        assert not second.done(), "the second writer must wait for the first one's lock"
        first.commit()
    await second

    versions = stored_versions(oracle, curve_id)
    assert [v["value"] for v in versions] == [2.61, 2.7, 2.8]
    assert [v["known_to"] for v in versions] == [
        versions[1]["known_from"],
        versions[2]["known_from"],
        OPEN,
    ]


def record_without_commit(connection: oracledb.Connection, version: Observation) -> None:
    """Record one version through the package and keep the transaction (and its locks) open."""
    list_type = connection.gettype("CORE.OBSERVATION_VERSION_LIST_T")
    element = list_type.element_type.newobject()
    element.CURVE_ID = version.curve_id
    element.MATURITY = version.maturity
    element.VALID_DATE = version.valid_date
    element.VALUE = version.value
    element.ORIGIN = version.origin.value
    element.SOURCE_ID = version.source_id
    element.RUN_ID = version.run_id
    element.CHANGE_REASON = version.change_reason.value
    with connection.cursor() as cursor:
        cursor.callproc(
            "core.core_observation.record_versions",
            [
                list_type.newobject([element]),
                cursor.var(oracledb.DB_TYPE_TIMESTAMP),
                cursor.var(oracledb.DB_TYPE_NUMBER),
            ],
        )


async def test_the_database_is_reachable(repository: OracleObservationRepository) -> None:
    assert await repository.is_reachable()


async def test_points_as_of_returns_the_grid_with_microsecond_as_of(
    repository: OracleObservationRepository, curve_id: str
) -> None:
    recorded = await repository.record_versions(
        [observation(curve_id, "2Y", "2.10"), observation(curve_id, "10Y", "2.61")]
    )

    points = await repository.points_as_of(curve_id, date(2026, 3, 12), recorded.known_from)
    before = await repository.points_as_of(
        curve_id, date(2026, 3, 12), recorded.known_from - timedelta(microseconds=1)
    )

    assert len(points) == 11
    assert [(p.maturity, p.months) for p in points][:4] == [
        ("3M", 3),
        ("6M", 6),
        ("1Y", 12),
        ("2Y", 24),
    ]
    assert {p.maturity: p.value for p in points}["2Y"] == 2.1
    assert {p.maturity: p.value for p in points}["10Y"] == 2.61
    assert all(p.value is None for p in before)
