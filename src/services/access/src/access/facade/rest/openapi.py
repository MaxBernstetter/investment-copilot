"""Export of the access OpenAPI document, the source of the published ``contracts/openapi`` file."""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from access.facade.rest.app import Services, create_app


@asynccontextmanager
async def _never() -> AsyncIterator[Services]:
    """The schema needs no backing services; the app must not open any."""
    raise RuntimeError("the OpenAPI export must not open services")
    yield


def render_openapi() -> str:
    app = create_app(_never, cors_origins=[])
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_openapi(), encoding="utf-8")


if __name__ == "__main__":
    main()
