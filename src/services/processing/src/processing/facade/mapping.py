"""Translation between contracts.processing.v1 and the domain."""

from decimal import Decimal

from contracts.processing import v1

from processing.domain.measures import CurveMeasures, MeasureInput, MeasurePoint
from processing.domain.quality import Finding
from processing.domain.read import (
    CurveValueQualities,
    QualityDayResult,
    QualityDays,
    RuleOutcome,
    ValueQualityResult,
)


def to_measures_response(measures: CurveMeasures) -> v1.MeasuresResponse:
    return v1.MeasuresResponse(
        data=v1.CurveMeasures(
            curve_id=measures.curve_id,
            valid_from=measures.valid_from,
            valid_to=measures.valid_to,
            points=[_measure_point(point) for point in measures.points],
        ),
        meta=v1.MeasuresMeta(as_of=measures.as_of, method_version=measures.method_version),
    )


def to_quality_days_response(days: QualityDays) -> v1.QualityDaysResponse:
    return v1.QualityDaysResponse(
        data=v1.QualityDays(
            curve_id=days.curve_id,
            valid_from=days.valid_from,
            valid_to=days.valid_to,
            days=[_quality_day(day) for day in days.days],
        ),
        meta=v1.QualityMeta(as_of=days.as_of),
    )


def to_value_quality_response(values: CurveValueQualities) -> v1.ValueQualityResponse:
    return v1.ValueQualityResponse(
        data=v1.ValueQualities(
            curve_id=values.curve_id,
            valid_from=values.valid_from,
            valid_to=values.valid_to,
            values=[_value_quality(value) for value in values.values],
        ),
        meta=v1.QualityMeta(as_of=values.as_of),
    )


def _quality_day(day: QualityDayResult) -> v1.QualityDay:
    return v1.QualityDay(
        valid_date=day.valid_date,
        status=v1.QualityStatus(day.status.value),
        run_id=day.run_id,
        checked_as_of=day.checked_as_of,
        rules=[_rule_outcome(rule) for rule in day.rules],
        findings=[_finding(finding) for finding in day.findings],
    )


def _value_quality(value: ValueQualityResult) -> v1.ValueQuality:
    return v1.ValueQuality(
        version_id=value.version_id,
        maturity=value.maturity,
        valid_date=value.valid_date,
        status=v1.QualityStatus(value.status.value),
        flags=[_finding(finding) for finding in value.flags],
    )


def _rule_outcome(outcome: RuleOutcome) -> v1.RuleOutcome:
    return v1.RuleOutcome(
        rule=v1.Rule(outcome.rule.value),
        outcome=v1.QualityStatus(outcome.outcome.value),
        finding_count=outcome.finding_count,
    )


def _finding(finding: Finding) -> v1.Finding:
    return v1.Finding(
        rule=v1.Rule(finding.rule.value),
        severity=v1.Severity(finding.severity.value),
        maturity=finding.maturity,
        version_id=finding.version_id,
        value=float(finding.value) if finding.value is not None else None,
        explanation=finding.explanation,
        evidence=finding.evidence,
    )


def _measure_point(point: MeasurePoint) -> v1.MeasurePoint:
    return v1.MeasurePoint(
        valid_date=point.valid_date,
        spread_2y_10y=_optional_float(point.spread_2y_10y),
        spread_3m_10y=_optional_float(point.spread_3m_10y),
        curvature_2y_5y_10y=_optional_float(point.curvature_2y_5y_10y),
        inverted=point.inverted,
        inputs=[_measure_input(item) for item in point.inputs],
        missing=list(point.missing),
        quality=v1.MeasureQuality(
            status=v1.QualityStatus(point.quality.status.value),
            flagged=list(point.quality.flagged),
        ),
    )


def _measure_input(item: MeasureInput) -> v1.MeasureInput:
    return v1.MeasureInput(
        maturity=item.maturity,
        value=float(item.value),
        version_id=item.version_id,
        status=v1.QualityStatus(item.status.value),
    )


def _optional_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
