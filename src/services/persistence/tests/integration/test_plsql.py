"""Runs the utPLSQL suites of the CORE packages (db/tests) inside the test container.

utPLSQL is installed into the container on demand from a pinned, checksum-verified
release, cached under PERSISTENCE_UTPLSQL_CACHE (default: <service>/.cache/utplsql).
"""

import hashlib
import io
import os
import re
import tarfile
import urllib.request
from pathlib import Path

import oracledb
import pytest
from docker.models.containers import Container

from tests.integration.conftest import ADMIN_PASSWORD, DB_DIR, SERVICE_NAME, OracleDatabase

UTPLSQL_VERSION = "3.2.2"
UTPLSQL_URL = (
    f"https://github.com/utPLSQL/utPLSQL/releases/download/v{UTPLSQL_VERSION}/utPLSQL.tar.gz"
)
UTPLSQL_SHA256 = "02bb981528e6f97f92b7faaced01ae56da91fe420aacf96624c5c12f4d4f1c5c"
CACHE_DIR = Path(
    os.environ.get(
        "PERSISTENCE_UTPLSQL_CACHE", Path(__file__).resolve().parents[2] / ".cache" / "utplsql"
    )
)
TEST_PACKAGES = sorted(DB_DIR.glob("tests/*.pks")) + sorted(DB_DIR.glob("tests/*.pkb"))
SUMMARY = re.compile(r"(\d+) tests?, (\d+) failed, (\d+) errored")


def utplsql_release() -> bytes:
    archive = CACHE_DIR / f"utPLSQL-{UTPLSQL_VERSION}.tar.gz"
    if not archive.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(UTPLSQL_URL, timeout=120) as response:
            archive.write_bytes(response.read())
    content = archive.read_bytes()
    if hashlib.sha256(content).hexdigest() != UTPLSQL_SHA256:
        archive.unlink()
        raise RuntimeError(f"checksum mismatch for {UTPLSQL_URL}")
    return content


def install_utplsql(oracle: OracleDatabase) -> None:
    container = oracle.container.get_wrapped_container()
    container.put_archive("/tmp", _single_file_tar("utplsql.tar.gz", utplsql_release()))
    _run_as_oracle(container, ["tar", "xzf", "/tmp/utplsql.tar.gz", "-C", "/tmp"], "/tmp")
    _run_as_oracle(
        container,
        [
            "sqlplus",
            "-s",
            "-L",
            f"sys/{ADMIN_PASSWORD}@//localhost/{SERVICE_NAME} as sysdba",
            "@install_headless.sql",
        ],
        "/tmp/utPLSQL/source",
    )


def _run_as_oracle(container: Container, command: list[str], workdir: str) -> None:
    exit_code, output = container.exec_run(command, workdir=workdir, user="oracle")
    assert isinstance(output, bytes)
    assert exit_code == 0, output.decode()[-4000:]


def _single_file_tar(name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def deploy_test_packages(connection: oracledb.Connection) -> None:
    with connection.cursor() as cursor:
        for package in TEST_PACKAGES:
            cursor.execute(package.read_text().strip().removesuffix("/"))
        cursor.execute(
            "select name, type, line, text from user_errors where name like 'UT\\_%' escape '\\'"
        )
        assert cursor.fetchall() == []


@pytest.fixture(scope="module")
def utplsql(oracle: OracleDatabase) -> OracleDatabase:
    install_utplsql(oracle)
    return oracle


def test_core_observation_package_suite_passes(utplsql: OracleDatabase) -> None:
    with utplsql.connect_as_owner() as connection:
        deploy_test_packages(connection)
        with connection.cursor() as cursor:
            cursor.execute("select * from table(ut.run('ut_core_observation'))")
            report = "\n".join(line or "" for (line,) in cursor)

    summary = SUMMARY.search(report)
    assert summary, report
    tests, failed, errored = (int(count) for count in summary.groups())
    assert (tests, failed, errored) == (25, 0, 0), report
