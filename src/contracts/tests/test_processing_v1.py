from typing import Any

import pytest
from pydantic import ValidationError

from contracts.processing.v1 import (
    Finding,
    MeasuresResponse,
    QualityDay,
    QualityStatus,
    Rule,
    RuleOutcome,
    Severity,
)


def quality_day(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "valid_date": "2026-10-07",
        "status": "warn",
        "run_id": "check-quality-ecb-aaa-spot-2026-10-07-2026-10-07",
        "checked_as_of": "2026-10-08T06:00:00Z",
        "rules": [{"rule": "missing-date", "outcome": "warn", "finding_count": 1}],
        "findings": [
            {
                "rule": "missing-date",
                "severity": "warn",
                "maturity": None,
                "version_id": None,
                "value": None,
                "explanation": "No value was published for this TARGET business day.",
                "evidence": "No value for any maturity on 2026-10-07",
            }
        ],
    }
    return fields | overrides


def test_quality_statuses() -> None:
    assert {status.value for status in QualityStatus} == {
        "passed",
        "info",
        "warn",
        "unchecked",
    }


def test_severity_is_warn_or_info() -> None:
    assert {severity.value for severity in Severity} == {"warn", "info"}


def test_a_quality_day_round_trips_json() -> None:
    day = QualityDay.model_validate(quality_day())

    assert day.rules == [
        RuleOutcome(rule=Rule.MISSING_DATE, outcome=QualityStatus.WARN, finding_count=1)
    ]
    assert day.findings[0] == Finding(
        rule=Rule.MISSING_DATE,
        severity=Severity.WARN,
        explanation="No value was published for this TARGET business day.",
        evidence="No value for any maturity on 2026-10-07",
    )
    assert QualityDay.model_validate_json(day.model_dump_json()) == day


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityDay.model_validate(quality_day(extra="not in the contract"))

    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "rule": "range",
                "severity": "warn",
                "explanation": "e",
                "evidence": "v",
                "unexpected": 1,
            }
        )


def measures_response(**point_overrides: Any) -> dict[str, Any]:
    point: dict[str, Any] = {
        "valid_date": "2026-10-08",
        "spread_2y_10y": 66.0,
        "spread_3m_10y": 71.0,
        "curvature_2y_5y_10y": None,
        "inverted": False,
        "inputs": [
            {"maturity": "3M", "value": 1.9, "version_id": 1, "status": "passed"},
            {"maturity": "2Y", "value": 1.95, "version_id": 2, "status": "passed"},
            {"maturity": "10Y", "value": 2.61, "version_id": 4, "status": "warn"},
        ],
        "missing": ["5Y"],
        "quality": {"status": "warn", "flagged": ["10Y"]},
    }
    return {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_from": "2026-10-08",
            "valid_to": "2026-10-08",
            "points": [point | point_overrides],
        },
        "meta": {"as_of": "2026-10-09T08:00:00Z", "method_version": "1"},
    }


def test_a_measures_response_round_trips_json() -> None:
    response = MeasuresResponse.model_validate(measures_response())

    point = response.data.points[0]
    assert point.curvature_2y_5y_10y is None
    assert point.missing == ["5Y"]
    assert point.quality.flagged == ["10Y"]
    assert point.inputs[2].status is QualityStatus.WARN
    assert MeasuresResponse.model_validate_json(response.model_dump_json()) == response


def test_measure_points_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MeasuresResponse.model_validate(measures_response(unexpected=1))


def test_measure_values_reject_nan() -> None:
    with pytest.raises(ValidationError):
        MeasuresResponse.model_validate(measures_response(spread_2y_10y=float("nan")))


def test_measures_meta_requires_a_timezone() -> None:
    body = measures_response()
    body["meta"]["as_of"] = "2026-10-09T08:00:00"

    with pytest.raises(ValidationError):
        MeasuresResponse.model_validate(body)


def test_measure_fields_are_required_but_nullable() -> None:
    body = measures_response()
    del body["data"]["points"][0]["spread_2y_10y"]

    with pytest.raises(ValidationError):
        MeasuresResponse.model_validate(body)
