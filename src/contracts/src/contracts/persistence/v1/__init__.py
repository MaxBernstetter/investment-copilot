"""Interface models of the persistence service, version 1."""

from contracts.persistence.v1.catalogue import (
    CURVES_PATH,
    Compounding,
    CurveDefinition,
    CurvesResponse,
    GridMaturity,
    RateType,
    Unit,
)
from contracts.persistence.v1.changes import (
    CURVE_CHANGES_PATH,
    ChangesMeta,
    CurveChanges,
    CurveChangesResponse,
    ValueChange,
)
from contracts.persistence.v1.curves import (
    CURVE_OBSERVATIONS_PATH,
    CurveMeta,
    CurveObservations,
    CurveObservationsResponse,
    CurvePoint,
)
from contracts.persistence.v1.observations import (
    MAX_BATCH_SIZE,
    RECORD_VERSIONS_PATH,
    ChangeReason,
    ObservationVersion,
    Origin,
    RecordVersionsRequest,
    RecordVersionsResponse,
)
from contracts.persistence.v1.series import (
    SERIES_OBSERVATIONS_PATH,
    SeriesObservations,
    SeriesObservationsResponse,
    SeriesPoint,
)
from contracts.persistence.v1.versions import (
    VALUE_VERSIONS_PATH,
    ValueVersion,
    ValueVersions,
    ValueVersionsResponse,
)

__all__ = [
    "CURVES_PATH",
    "CURVE_CHANGES_PATH",
    "CURVE_OBSERVATIONS_PATH",
    "MAX_BATCH_SIZE",
    "RECORD_VERSIONS_PATH",
    "SERIES_OBSERVATIONS_PATH",
    "VALUE_VERSIONS_PATH",
    "ChangeReason",
    "ChangesMeta",
    "Compounding",
    "CurveChanges",
    "CurveChangesResponse",
    "CurveDefinition",
    "CurveMeta",
    "CurveObservations",
    "CurveObservationsResponse",
    "CurvePoint",
    "CurvesResponse",
    "GridMaturity",
    "ObservationVersion",
    "Origin",
    "RateType",
    "RecordVersionsRequest",
    "RecordVersionsResponse",
    "SeriesObservations",
    "SeriesObservationsResponse",
    "SeriesPoint",
    "Unit",
    "ValueChange",
    "ValueVersion",
    "ValueVersions",
    "ValueVersionsResponse",
]
