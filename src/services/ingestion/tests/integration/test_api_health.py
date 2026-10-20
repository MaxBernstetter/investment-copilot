"""Readiness of the ingestion api against a migrated ING schema."""

import pytest
from pydantic import SecretStr

from ingestion.config import DatabaseSettings
from ingestion.infrastructure.ing.pool import OracleHealth, create_pool
from tests.integration.conftest import APP_PASSWORD, OracleDatabase

pytestmark = pytest.mark.anyio


async def test_ready_against_the_migrated_database(oracle: OracleDatabase) -> None:
    settings = DatabaseSettings(dsn=oracle.dsn, password=SecretStr(APP_PASSWORD))
    pool = create_pool(settings)
    try:
        assert await OracleHealth(pool, call_timeout_ms=settings.call_timeout_ms).is_reachable()
    finally:
        await pool.close()
