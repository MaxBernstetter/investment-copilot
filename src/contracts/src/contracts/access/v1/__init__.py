"""Interface models of the access service, version 1."""

from contracts.access.v1.curves import (
    CURVE_OBSERVATIONS_PATH,
    CurveMeta,
    CurveObservations,
    CurveObservationsResponse,
    CurvePoint,
    Problem,
)
from contracts.access.v1.series import (
    SERIES_OBSERVATIONS_PATH,
    SeriesObservations,
    SeriesObservationsResponse,
    SeriesPoint,
)

__all__ = [
    "CURVE_OBSERVATIONS_PATH",
    "SERIES_OBSERVATIONS_PATH",
    "CurveMeta",
    "CurveObservations",
    "CurveObservationsResponse",
    "CurvePoint",
    "Problem",
    "SeriesObservations",
    "SeriesObservationsResponse",
    "SeriesPoint",
]
