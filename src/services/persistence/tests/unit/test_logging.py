import json
import logging
import logging.config
from io import StringIO
from pathlib import Path

import pytest

LOG_CONFIG = Path(__file__).parents[2] / "log_config.json"


def test_log_config_writes_json_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    logging.config.dictConfig(json.loads(LOG_CONFIG.read_text(encoding="utf-8")))
    handler = logging.getHandlerByName("stderr")
    assert isinstance(handler, logging.StreamHandler)
    stream = StringIO()
    monkeypatch.setattr(handler, "stream", stream)

    logging.getLogger("persistence.test").info("persistence is ready")

    line = stream.getvalue().strip().splitlines()[-1]
    assert json.loads(line)["message"] == "persistence is ready"
