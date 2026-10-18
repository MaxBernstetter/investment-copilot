"""Integration fixtures: a real Garage node, prepared by the same setup script as locally.

One container per test session (Testcontainers). ``spool/setup.sh`` runs against it
through ``docker exec``, exactly as ``task ingestion:spool:setup`` runs it through Compose.
"""

import os
import secrets
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer

from ingestion.config import SpoolSettings

GARAGE_IMAGE = os.environ.get("INGESTION_GARAGE_IMAGE", "dxflrs/garage:v2.4.1")
SPOOL_DIR = Path(__file__).resolve().parents[2] / "spool"

# Throwaway credentials of the test container; never used outside it.
BUCKET_URL = "s3://ingestion-spool"
KEY_ID = "GK" + "0" * 24
SECRET_KEY = "0" * 64


@pytest.fixture(scope="session")
def garage() -> Iterator[SpoolSettings]:
    container = (
        DockerContainer(GARAGE_IMAGE)
        .with_env("GARAGE_RPC_SECRET", secrets.token_hex(32))
        .with_env("GARAGE_ADMIN_TOKEN", secrets.token_hex(16))
        .with_volume_mapping(str(SPOOL_DIR / "garage.toml"), "/etc/garage.toml", "ro")
        .with_exposed_ports(3900)
    )
    with container:
        subprocess.run(
            [str(SPOOL_DIR / "setup.sh")],
            env=os.environ
            | {
                "GARAGE": f"docker exec {container.get_wrapped_container().id} /garage",
                "INGESTION_SPOOL__URL": BUCKET_URL,
                "INGESTION_SPOOL__ACCESS_KEY_ID": KEY_ID,
                "INGESTION_SPOOL__SECRET_ACCESS_KEY": SECRET_KEY,
            },
            check=True,
        )
        host = container.get_container_host_ip()
        port = container.get_exposed_port(3900)
        yield SpoolSettings.model_validate(
            {
                "url": BUCKET_URL,
                "endpoint": f"http://{host}:{port}",
                "access_key_id": KEY_ID,
                "secret_access_key": SECRET_KEY,
            }
        )
