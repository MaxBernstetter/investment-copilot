"""Client of the persistence service (its write interface)."""

from ingestion.infrastructure.persistence.client import (
    PersistenceClient,
    PersistenceUnavailableError,
    PersistenceWriteError,
)

__all__ = ["PersistenceClient", "PersistenceUnavailableError", "PersistenceWriteError"]
