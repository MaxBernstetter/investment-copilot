"""Run ingestion and processing job CLIs in Docker from Airflow tasks."""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterable, Sequence

from airflow.providers.docker.hooks.docker import DockerHook
from airflow.sdk.exceptions import AirflowFailException
from docker.errors import APIError

IMAGE_ENV = {
    "ingestion-load-ecb": "YIELDLENS_INGESTION_JOB_IMAGE",
    "processing-check-quality": "YIELDLENS_PROCESSING_JOB_IMAGE",
}
JOB_OTEL_ENDPOINT_ENV = "YIELDLENS_JOB_OTEL_ENDPOINT"
OTEL_SERVICE_NAMES = {
    "ingestion-load-ecb": "ingestion-job",
    "processing-check-quality": "processing-job",
}

USAGE_OR_CONFIGURATION_ERROR = 2
RUN_TIMEOUT_SECONDS = 30 * 60
STOP_TIMEOUT_SECONDS = 10

log = logging.getLogger(__name__)


class JobFailedError(Exception):
    """The job ended with a status that a retry may fix."""


def job_container_env(binary: str) -> dict[str, str]:
    """Env vars for the job container: the worker's INGESTION_/PROCESSING_ keys, plus OTEL_* when
    YIELDLENS_JOB_OTEL_ENDPOINT is non-empty (observability profile on)."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.startswith(("INGESTION_", "PROCESSING_"))
    }
    endpoint = os.environ.get(JOB_OTEL_ENDPOINT_ENV, "")
    if endpoint:
        environment["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
        environment["OTEL_SERVICE_NAME"] = OTEL_SERVICE_NAMES[binary]
        environment["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    return environment


def image_for(binary: str) -> str:
    env_key = IMAGE_ENV.get(binary)
    if env_key is None:
        raise AirflowFailException(f"unknown job binary {binary!r}")
    image = os.environ.get(env_key)
    if not image:
        raise AirflowFailException(f"job image not configured ({env_key} is unset)")
    return image


def _log_chunk(line: str | bytes) -> str:
    if isinstance(line, bytes):
        return line.decode(encoding="utf-8", errors="replace")
    return line


def _stream_container_logs(log_stream: Iterable[str | bytes]) -> None:
    buffer = ""
    for log_chunk_raw in log_stream:
        buffer += _log_chunk(log_chunk_raw)
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            log.info(line.rstrip())
    if buffer:
        log.info(buffer.rstrip())


def _docker_hook() -> DockerHook:
    docker_url = os.environ.get("DOCKER_HOST", "unix://var/run/docker.sock")
    return DockerHook(docker_conn_id=None, base_url=docker_url)


def run_job_container(command: Sequence[str]) -> None:
    """Run ``command[0]`` as the container entrypoint with the rest as argv."""
    binary = command[0]
    argv = list(command[1:])
    image = image_for(binary)
    environment = job_container_env(binary)
    network_mode = os.environ["YIELDLENS_DOCKER_NETWORK"]

    hook = _docker_hook()
    cli = hook.get_conn()
    container: dict[str, str] | None = None
    try:
        container = cli.create_container(
            image=image,
            entrypoint=binary,
            command=argv,
            environment=environment,
            host_config=cli.create_host_config(
                auto_remove=True,
                network_mode=network_mode,
            ),
        )
        container_id = container["Id"]
        log_stream = cli.attach(container=container_id, stdout=True, stderr=True, stream=True)
        cli.start(container_id)
        _stream_container_logs(log_stream)
        result = cli.wait(container_id, timeout=RUN_TIMEOUT_SECONDS)
        exit_code = result["StatusCode"]
        if exit_code == USAGE_OR_CONFIGURATION_ERROR:
            raise AirflowFailException(f"{binary} ended with exit status 2 (usage or config)")
        if exit_code != 0:
            raise JobFailedError(f"{binary} ended with exit status {exit_code}")
    finally:
        if container is not None:
            with contextlib.suppress(APIError):
                cli.stop(container["Id"], timeout=STOP_TIMEOUT_SECONDS)
