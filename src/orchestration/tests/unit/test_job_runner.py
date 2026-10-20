from unittest.mock import MagicMock, patch

import pytest
from airflow.sdk.exceptions import AirflowFailException

from orchestration.job_runner import (
    IMAGE_ENV,
    JobFailedError,
    image_for,
    job_container_env,
    run_job_container,
)


@pytest.fixture
def job_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YIELDLENS_INGESTION_JOB_IMAGE", "yieldlens-ingestion:local")
    monkeypatch.setenv("YIELDLENS_PROCESSING_JOB_IMAGE", "yieldlens-processing:local")
    monkeypatch.setenv("YIELDLENS_DOCKER_NETWORK", "yieldlens-dev_default")
    monkeypatch.setenv("INGESTION_PERSISTENCE__URL", "http://persistence:8001")
    monkeypatch.setenv("PROCESSING_PERSISTENCE__URL", "http://persistence:8001")
    monkeypatch.setenv("OTHER_SECRET", "must-not-forward")


def test_image_env_maps_job_binaries_to_stack_variables() -> None:
    assert IMAGE_ENV["ingestion-load-ecb"] == "YIELDLENS_INGESTION_JOB_IMAGE"
    assert IMAGE_ENV["processing-check-quality"] == "YIELDLENS_PROCESSING_JOB_IMAGE"


def test_image_for_reads_configured_job_image(job_env: None) -> None:
    assert image_for("ingestion-load-ecb") == "yieldlens-ingestion:local"


def test_missing_job_image_raises_fail_exception(
    job_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YIELDLENS_INGESTION_JOB_IMAGE")
    with pytest.raises(AirflowFailException, match="YIELDLENS_INGESTION_JOB_IMAGE"):
        image_for("ingestion-load-ecb")


def test_job_container_env_forwards_only_ingestion_and_processing_keys(job_env: None) -> None:
    forwarded = job_container_env()
    assert forwarded["INGESTION_PERSISTENCE__URL"] == "http://persistence:8001"
    assert forwarded["PROCESSING_PERSISTENCE__URL"] == "http://persistence:8001"
    assert all(key.startswith(("INGESTION_", "PROCESSING_")) for key in forwarded)
    assert "OTHER_SECRET" not in forwarded


@patch("orchestration.job_runner._docker_hook")
def test_run_job_container_strips_binary_and_passes_argv(
    mock_hook_factory: MagicMock, job_env: None
) -> None:
    cli = MagicMock()
    cli.create_container.return_value = {"Id": "cid"}
    cli.wait.return_value = {"StatusCode": 0}
    mock_hook_factory.return_value.get_conn.return_value = cli

    run_job_container(
        ["ingestion-load-ecb", "daily", "--valid-date", "2026-10-16", "--run-id", "run-1"]
    )

    create_kwargs = cli.create_container.call_args.kwargs
    assert create_kwargs["image"] == "yieldlens-ingestion:local"
    assert create_kwargs["entrypoint"] == "ingestion-load-ecb"
    assert create_kwargs["command"] == ["daily", "--valid-date", "2026-10-16", "--run-id", "run-1"]
    host_config = cli.create_host_config.call_args.kwargs
    assert host_config["network_mode"] == "yieldlens-dev_default"
    assert host_config["auto_remove"] is True
    assert create_kwargs["environment"] == job_container_env()


@patch("orchestration.job_runner._stream_container_logs")
@patch("orchestration.job_runner._docker_hook")
def test_run_job_container_maps_exit_code_two_to_fail_exception(
    mock_hook_factory: MagicMock,
    mock_stream_logs: MagicMock,
    job_env: None,
) -> None:
    cli = MagicMock()
    cli.create_container.return_value = {"Id": "cid"}
    cli.wait.return_value = {"StatusCode": 2}
    mock_hook_factory.return_value.get_conn.return_value = cli

    with pytest.raises(AirflowFailException, match="exit status 2"):
        run_job_container(["ingestion-load-ecb", "daily"])

    mock_stream_logs.assert_called_once()


@patch("orchestration.job_runner._docker_hook")
def test_run_job_container_maps_other_nonzero_exit_to_job_failed(
    mock_hook_factory: MagicMock,
    job_env: None,
) -> None:
    cli = MagicMock()
    cli.create_container.return_value = {"Id": "cid"}
    cli.wait.return_value = {"StatusCode": 1}
    mock_hook_factory.return_value.get_conn.return_value = cli

    with pytest.raises(JobFailedError, match="exit status 1"):
        run_job_container(["ingestion-load-ecb", "daily"])
