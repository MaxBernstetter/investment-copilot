"""Translation between the domain and the public contract (contracts.access.v1)."""

from collections.abc import Mapping, Sequence
from datetime import UTC

from contracts.access import v1

from access.domain.catalogue import CurveDefinition
from access.domain.changes import CurveChanges
from access.domain.curve import CurveAsOf
from access.domain.quality import ValueQuality, quality_for
from access.domain.quality_days import QualityDays
from access.domain.series import Series
from access.domain.versions import ValueVersions


def to_response(
    curve: CurveAsOf, *, known: Mapping[int, ValueQuality] | None, attribution: str
) -> v1.CurveObservationsResponse:
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
                    origin=v1.Origin.PUBLISHED,
                    quality=_point_quality(point.value, point.version_id, known),
                )
                for point in curve.points
            ],
        ),
        meta=v1.CurveMeta(
            as_of=curve.as_of.astimezone(UTC),
            source_attribution=attribution,
        ),
    )


def to_series_response(
    series: Series, *, known: Mapping[int, ValueQuality] | None, attribution: str
) -> v1.SeriesObservationsResponse:
    return v1.SeriesObservationsResponse(
        data=v1.SeriesObservations(
            curve_id=series.curve_id,
            maturity=series.maturity,
            points=[
                v1.SeriesPoint(
                    valid_date=point.valid_date,
                    value=point.value,
                    version_id=point.version_id,
                    origin=v1.Origin.PUBLISHED,
                    quality=_to_contract(quality_for(point.version_id, known)),
                )
                for point in series.points
            ],
        ),
        meta=v1.CurveMeta(
            as_of=series.as_of.astimezone(UTC),
            source_attribution=attribution,
        ),
    )


def to_versions_response(versions: ValueVersions, *, attribution: str) -> v1.ValueVersionsResponse:
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
        meta=v1.CurveMeta(
            as_of=versions.as_of.astimezone(UTC),
            source_attribution=attribution,
        ),
    )


def to_quality_days_response(days: QualityDays, *, attribution: str) -> v1.QualityDaysResponse:
    return v1.QualityDaysResponse(
        data=v1.QualityDays(
            curve_id=days.curve_id,
            valid_from=days.valid_from,
            valid_to=days.valid_to,
            days=[
                v1.QualityDay(
                    valid_date=day.valid_date,
                    status=v1.QualityStatus(day.status),
                    run_id=day.run_id,
                    checked_as_of=day.checked_as_of,
                    rules=[
                        v1.RuleOutcome(
                            rule=v1.Rule(rule.rule),
                            outcome=v1.QualityStatus(rule.outcome),
                            finding_count=rule.finding_count,
                        )
                        for rule in day.rules
                    ],
                    findings=[
                        v1.QualityFinding(
                            rule=v1.Rule(finding.rule),
                            severity=v1.Severity(finding.severity),
                            maturity=finding.maturity,
                            version_id=finding.version_id,
                            value=finding.value,
                            explanation=finding.explanation,
                            evidence=finding.evidence,
                        )
                        for finding in day.findings
                    ],
                )
                for day in days.days
            ],
        ),
        meta=v1.QualityMeta(
            as_of=days.as_of.astimezone(UTC),
            source_attribution=attribution,
        ),
    )


def to_changes_response(changes: CurveChanges, *, attribution: str) -> v1.CurveChangesResponse:
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
            since=changes.since.astimezone(UTC),
            as_of=changes.as_of.astimezone(UTC),
            source_attribution=attribution,
        ),
    )


def to_curves_response(curves: Sequence[CurveDefinition]) -> v1.CurvesResponse:
    return v1.CurvesResponse(
        data=[
            v1.CurveDefinition(
                curve_id=curve.curve_id,
                label=curve.label,
                source_id=curve.source_id,
                area=curve.area,
                attribution=curve.attribution,
                rate_type=v1.RateType(curve.rate_type),
                compounding=v1.Compounding(curve.compounding),
                unit=v1.Unit(curve.unit),
                source_model=curve.source_model,
                simulated=curve.simulated,
                maturities=[
                    v1.GridMaturity(maturity=maturity.maturity, months=maturity.months)
                    for maturity in curve.maturities
                ],
            )
            for curve in curves
        ]
    )


def _point_quality(
    value: float | None, version_id: int | None, known: Mapping[int, ValueQuality] | None
) -> v1.ValueQuality | None:
    if value is None or version_id is None:
        return None
    return _to_contract(quality_for(version_id, known))


def _to_contract(quality: ValueQuality) -> v1.ValueQuality:
    return v1.ValueQuality(
        status=v1.QualityStatus(quality.status),
        flags=[
            v1.QualityFlag(
                rule=flag.rule,
                severity=v1.Severity(flag.severity),
                explanation=flag.explanation,
                evidence=flag.evidence,
            )
            for flag in quality.flags
        ],
    )
