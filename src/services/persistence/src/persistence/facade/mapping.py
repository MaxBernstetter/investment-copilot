"""Translation between the published contract (contracts.persistence.v1) and the domain."""

from contracts.persistence import v1

from persistence.domain.curve import CurveAsOf
from persistence.domain.observation import ChangeReason, Observation, Origin, RecordedVersions


def to_observation(version: v1.ObservationVersion) -> Observation:
    return Observation(
        curve_id=version.curve_id,
        maturity=version.maturity,
        valid_date=version.valid_date,
        value=version.value,
        origin=Origin(version.origin.value),
        method_version=version.method_version,
        source_id=version.source_id,
        run_id=version.run_id,
        change_reason=ChangeReason(version.change_reason.value),
        normalization_version=version.normalization_version,
        delivery_id=version.delivery_id,
    )


def to_response(recorded: RecordedVersions) -> v1.RecordVersionsResponse:
    return v1.RecordVersionsResponse(
        recorded_count=recorded.recorded_count,
        unchanged_count=recorded.unchanged_count,
        known_from=recorded.known_from,
    )


def to_curve_response(curve: CurveAsOf) -> v1.CurveObservationsResponse:
    return v1.CurveObservationsResponse(
        data=v1.CurveObservations(
            curve_id=curve.curve_id,
            valid_date=curve.valid_date,
            points=[
                v1.CurvePoint(maturity=point.maturity, months=point.months, value=point.value)
                for point in curve.points
            ],
        ),
        meta=v1.CurveMeta(as_of=curve.as_of),
    )
