"""Client of the persistence service (its write interface)."""

from ingestion.infrastructure.persistence.client import PersistenceClient, PersistenceWriteError

__all__ = ["PersistenceClient", "PersistenceWriteError"]
