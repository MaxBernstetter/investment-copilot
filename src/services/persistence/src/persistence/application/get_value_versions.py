"""Use case: read the version history of one published value as known at a time."""

from datetime import date, datetime
from typing import Protocol

from persistence.application.knowledge_time import resolve_as_of
from persistence.domain.curve import NothingKnownError
from persistence.domain.versions import ValueVersion, ValueVersions


class ValueVersionReader(Protocol):
    """Port to the bitemporal store: reads the versions of a value as of a knowledge time."""

    async def current_knowledge_time(self) -> datetime:
        """The knowledge time now, from the database clock (UTC)."""
        ...

    async def knowledge_horizon(self) -> datetime:
        """The knowledge time of the latest committed write, in UTC."""
        ...

    async def has_maturity(self, curve_id: str, maturity: str) -> bool:
        """Whether the maturity is on the grid of the curve; False if the curve is undefined."""
        ...

    async def value_versions(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime
    ) -> list[ValueVersion]:
        """Published versions known at ``as_of``, oldest first; ``known_to`` hidden if current."""
        ...


class GetValueVersions:
    def __init__(self, reader: ValueVersionReader) -> None:
        self._reader = reader

    async def __call__(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime | None
    ) -> ValueVersions:
        as_of = await resolve_as_of(self._reader, as_of)

        if not await self._reader.has_maturity(curve_id, maturity):
            raise NothingKnownError(f"Maturity {maturity} is not on the grid of curve {curve_id}")

        versions = await self._reader.value_versions(curve_id, maturity, valid_date, as_of)
        if not versions:
            raise NothingKnownError(
                f"No published value of {maturity} of curve {curve_id} for {valid_date} "
                f"is known as of {as_of.isoformat()}"
            )
        return ValueVersions(
            curve_id=curve_id,
            maturity=maturity,
            valid_date=valid_date,
            as_of=as_of,
            versions=tuple(versions),
        )
