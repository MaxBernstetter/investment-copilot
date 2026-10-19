"""Translation between the domain and the public contract (contracts.access.v1)."""

from datetime import UTC

from contracts.access import v1

from access.domain.changes import CurveChanges
from access.domain.curve import CurveAsOf
from access.domain.series import Series
from access.domain.versions import ValueVersions


def to_response(curve: CurveAsOf) -> v1.CurveObservationsResponse:
    return v1.CurveObservationsResponse(
        data=v1.CurveObservations(
            curve_id=curve.curve_id,
            valid_date=curve.valid_date,
            points=[
                v1.CurvePoint(maturity=point.maturity, months=point.months, value=point.value)
                for point in curve.points
            ],
        ),
        meta=v1.CurveMeta(as_of=curve.as_of.astimezone(UTC)),
    )


def to_series_response(series: Series) -> v1.SeriesObservationsResponse:
    return v1.SeriesObservationsResponse(
        data=v1.SeriesObservations(
            curve_id=series.curve_id,
            maturity=series.maturity,
            points=[
                v1.SeriesPoint(valid_date=point.valid_date, value=point.value)
                for point in series.points
            ],
        ),
        meta=v1.CurveMeta(as_of=series.as_of.astimezone(UTC)),
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
        meta=v1.CurveMeta(as_of=versions.as_of.astimezone(UTC)),
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
        meta=v1.ChangesMeta(
            since=changes.since.astimezone(UTC), as_of=changes.as_of.astimezone(UTC)
        ),
    )
