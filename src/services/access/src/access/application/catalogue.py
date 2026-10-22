"""The curve catalogue, cached in process for a while (reference data)."""

import logging
import time
from collections.abc import Callable

from access.application.ports import CatalogueReader
from access.domain.catalogue import CurveDefinition
from access.domain.curve import CurveNotFoundError, PersistenceUnavailableError

logger = logging.getLogger(__name__)


class CachedCatalogue:
    """The curve catalogue, reread from persistence at most once per TTL.

    When a reread fails after a catalogue was loaded, the last good catalogue is served and the
    next request tries again. Only when no catalogue was ever loaded does the failure propagate.
    """

    def __init__(
        self,
        reader: CatalogueReader,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._reader = reader
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._curves: tuple[CurveDefinition, ...] | None = None
        self._loaded_at = 0.0

    async def curves(self) -> tuple[CurveDefinition, ...]:
        expired = self._curves is None or self._clock() - self._loaded_at >= self._ttl_seconds
        if not expired:
            assert self._curves is not None
            return self._curves
        try:
            curves = await self._reader.curves()
        except PersistenceUnavailableError:
            if self._curves is None:
                raise
            logger.warning("curve catalogue refresh failed; serving the last loaded catalogue")
            return self._curves
        self._curves = curves
        self._loaded_at = self._clock()
        return curves

    async def attribution(self, curve_id: str) -> str:
        for curve in await self.curves():
            if curve.curve_id == curve_id:
                return curve.attribution
        raise CurveNotFoundError(f"no curve named {curve_id}")
