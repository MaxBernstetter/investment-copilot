"""Translation between the published contract (contracts.persistence.v1) and the domain."""

from contracts.persistence import v1

from persistence.domain.changes import CurveChanges
from persistence.domain.curve import CurveAsOf
from persistence.domain.observation import ChangeReason, Observation, Origin, RecordedVersions
from persistence.domain.series import Series
from persistence.domain.versions import ValueVersions


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
                v1.CurvePoint(
                    maturity=point.maturity,
                    months=point.months,
                    value=point.value,
                    version_id=point.version_id,
                )
                for point in curve.points
            ],
        ),
        meta=v1.CurveMeta(as_of=curve.as_of),
    )


def to_series_response(series: Series) -> v1.SeriesObservationsResponse:
    return v1.SeriesObservationsResponse(
        data=v1.SeriesObservations(
            curve_id=series.curve_id,
            maturity=series.maturity,
            points=[
                v1.SeriesPoint(
                    valid_date=point.valid_date, value=point.value, version_id=point.version_id
                )
                for point in series.points
            ],
        ),
        meta=v1.CurveMeta(as_of=series.as_of),
    )


def to_versions_response(versions: ValueVersions) -> v1.ValueVersionsResponse:
    return v1.ValueVersionsResponse(
        data=v1.ValueVersions(
            curve_id=versions.curve_id,
            maturity=versions.maturity,
            valid_date=versions.valid_date,
            versions=[
                v1.ValueVersion(
                    version_id=version.version_id,
                    value=version.value,
                    known_from=version.known_from,
                    known_to=version.known_to,
                    source_id=version.source_id,
                    run_id=version.run_id,
                    change_reason=v1.ChangeReason(version.change_reason.value),
                    normalization_version=version.normalization_version,
                    delivery_id=version.delivery_id,
                )
                for version in versions.versions
            ],
        ),
        meta=v1.CurveMeta(as_of=versions.as_of),
    )


def to_changes_response(changes: CurveChanges) -> v1.CurveChangesResponse:
    return v1.CurveChangesResponse(
        data=v1.CurveChanges(
            curve_id=changes.curve_id,
            valid_from=changes.valid_from,
            valid_to=changes.valid_to,
            changes=[
                v1.ValueChange(
                    valid_date=change.valid_date,
                    maturity=change.maturity,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    change_reason=v1.ChangeReason(change.change_reason.value),
                    source_id=change.source_id,
                    known_from=change.known_from,
                )
                for change in changes.changes
            ],
        ),
        meta=v1.ChangesMeta(since=changes.since, as_of=changes.as_of),
    )
