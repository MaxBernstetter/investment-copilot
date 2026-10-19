from datetime import date
from typing import Any

import oracledb

from tests.integration.conftest import OracleDatabase

RECORD_ONE = """
declare
  l_versions core.observation_version_list_t := core.observation_version_list_t(
    core.observation_version_t(
      :curve_id, '10Y', date '2026-03-12', :value, 'published', null,
      'ecb', 'it-run', 'revision', '1', 'it-delivery'
    )
  );
  l_known_from timestamp;
  l_count pls_integer;
begin
  core.core_observation.record_versions(l_versions, l_known_from, l_count);
  :known_from := l_known_from;
end;
"""


def record_one(connection: oracledb.Connection, curve_id: str, value: float) -> Any:
    """Records one revision in the caller's transaction; the caller decides when to commit."""
    with connection.cursor() as cursor:
        known_from = cursor.var(oracledb.DB_TYPE_TIMESTAMP)
        cursor.execute(RECORD_ONE, curve_id=curve_id, value=value, known_from=known_from)
        return known_from.getvalue()


def horizon(connection: oracledb.Connection) -> Any:
    with connection.cursor() as cursor:
        return cursor.callfunc(
            "core.core_observation.knowledge_horizon", oracledb.DB_TYPE_TIMESTAMP
        )


def curve_as_of(connection: oracledb.Connection, curve_id: str, as_of: Any) -> list[Any]:
    with connection.cursor() as cursor:
        points = cursor.callfunc(
            "core.core_observation.get_as_of",
            oracledb.DB_TYPE_CURSOR,
            [curve_id, date(2026, 3, 12), as_of],
        )
        return list(points.fetchall())


def test_an_as_of_read_at_the_horizon_is_unchanged_by_a_write_committed_later(
    oracle: OracleDatabase, curve_id: str
) -> None:
    with oracle.connect_as_app() as writer, oracle.connect_as_app() as reader:
        # A committed revision establishes the horizon that the reader observes.
        record_one(writer, curve_id, 2.10)
        writer.commit()

        # The writer records a revision it does not commit yet.
        pending_known_from = record_one(writer, curve_id, 2.20)
        read_horizon = horizon(reader)
        before = curve_as_of(reader, curve_id, read_horizon)

        writer.commit()

        assert pending_known_from > read_horizon
        assert horizon(reader) == pending_known_from
        assert curve_as_of(reader, curve_id, read_horizon) == before
