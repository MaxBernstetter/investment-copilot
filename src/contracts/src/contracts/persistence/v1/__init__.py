"""Interface models of the persistence service, version 1."""

from contracts.persistence.v1.observations import (
    MAX_BATCH_SIZE,
    RECORD_VERSIONS_PATH,
    ChangeReason,
    ObservationVersion,
    Origin,
    RecordVersionsRequest,
    RecordVersionsResponse,
)

__all__ = [
    "MAX_BATCH_SIZE",
    "RECORD_VERSIONS_PATH",
    "ChangeReason",
    "ObservationVersion",
    "Origin",
    "RecordVersionsRequest",
    "RecordVersionsResponse",
]
