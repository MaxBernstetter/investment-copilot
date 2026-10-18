"""The delivery spool: fetched windows kept while persistence is unavailable."""

from ingestion.infrastructure.spool.object_store import ObjectStoreSpool, open_spool

__all__ = ["ObjectStoreSpool", "open_spool"]
