"""Client of the persistence service's readiness probe."""

from types import TracebackType
from typing import Self

import httpx


class PersistenceClient:
    """Asks the persistence service whether it is ready to serve."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def is_ready(self) -> bool:
        """True only when persistence answers ``200`` on ``/ready``; unreachable is not ready."""
        try:
            response = await self._http.get("/ready")
        except httpx.HTTPError:
            return False
        return response.status_code == httpx.codes.OK
