"""Integration fixtures: a real Oracle Free container with the CORE migrations applied.

One container per test session (Testcontainers). Migrations run through the
same Liquibase image and changelogs as ``task persistence:db:migrate``.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import docker
import oracledb
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

ORACLE_IMAGE = os.environ.get("PERSISTENCE_ORACLE_IMAGE", "gvenzl/oracle-free:23-slim-faststart")
LIQUIBASE_IMAGE = os.environ.get("PERSISTENCE_LIQUIBASE_IMAGE", "liquibase/liquibase:4.33.0")
DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORACLE_ALIAS = "oracle"
SERVICE_NAME = "FREEPDB1"

# Throwaway credentials of the test container; never used outside it.
ADMIN_PASSWORD = "Admin_test_1"
OWNER_PASSWORD = "Owner_test_1"
APP_PASSWORD = "App_test_1"


@dataclass(frozen=True, slots=True)
class OracleDatabase:
    container: DockerContainer
    network: Network
    host: str
    port: int

    @property
    def dsn(self) -> str:
        return f"{self.host}:{self.port}/{SERVICE_NAME}"

    def connect_as_owner(self) -> oracledb.Connection:
        return oracledb.connect(user="core", password=OWNER_PASSWORD, dsn=self.dsn)

    def connect_as_app(self) -> oracledb.Connection:
        return oracledb.connect(user="core_app", password=APP_PASSWORD, dsn=self.dsn)

    def migrate(self) -> str:
        """Apply the admin and the CORE changelog; returns the Liquibase output."""
        admin = run_liquibase(self.network, "admin/changelog.yaml", "system", ADMIN_PASSWORD)
        core = run_liquibase(self.network, "core/changelog.yaml", "core", OWNER_PASSWORD)
        return admin + core


def run_liquibase(network: Network, changelog: str, username: str, password: str) -> str:
    output: bytes = docker.from_env().containers.run(
        LIQUIBASE_IMAGE,
        command=[
            "--search-path=/liquibase/changelog",
            "update",
            f"--changelog-file={changelog}",
        ],
        environment={
            "LIQUIBASE_COMMAND_URL": f"jdbc:oracle:thin:@//{ORACLE_ALIAS}:1521/{SERVICE_NAME}",
            "LIQUIBASE_COMMAND_USERNAME": username,
            "LIQUIBASE_COMMAND_PASSWORD": password,
            "LIQUIBASE_SHOW_BANNER": "false",
            "CORE_PASSWORD": OWNER_PASSWORD,
            "CORE_APP_PASSWORD": APP_PASSWORD,
        },
        network=network.name,
        volumes={str(DB_DIR): {"bind": "/liquibase/changelog", "mode": "ro"}},
        remove=True,
        stdout=True,
        stderr=True,
    )
    return output.decode()


@pytest.fixture(scope="session")
def oracle() -> Iterator[OracleDatabase]:
    with Network() as network:
        container = (
            DockerContainer(ORACLE_IMAGE)
            .with_env("ORACLE_PASSWORD", ADMIN_PASSWORD)
            .with_exposed_ports(1521)
            .with_network(network)
            .with_network_aliases(ORACLE_ALIAS)
            .waiting_for(
                LogMessageWaitStrategy("DATABASE IS READY TO USE!").with_startup_timeout(600)
            )
        )
        with container:
            database = OracleDatabase(
                container=container,
                network=network,
                host=container.get_container_host_ip(),
                port=int(container.get_exposed_port(1521)),
            )
            database.migrate()
            yield database
