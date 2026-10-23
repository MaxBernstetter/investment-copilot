from typing import Any

import pytest
from pydantic import ValidationError

from contracts.access import v1


def curve_response(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_date": "2026-03-12",
            "points": [
                {
                    "maturity": "3M",
                    "months": 3,
                    "value": None,
                    "version_id": None,
                    "origin": "published",
                    "quality": None,
                },
                {
                    "maturity": "10Y",
                    "months": 120,
                    "value": 2.61,
                    "version_id": 7,
                    "origin": "published",
                    "quality": {"status": "passed", "flags": []},
                },
            ],
        },
        "meta": {"as_of": "2026-03-13T09:00:00Z", "source_attribution": "Source: ECB statistics"},
    }
    return body | overrides


def test_curve_response_round_trips_with_missing_points() -> None:
    response = v1.CurveObservationsResponse.model_validate(curve_response())

    assert response.data.points[0].value is None
    assert response.data.points[1].value == 2.61
    assert v1.CurveObservationsResponse.model_validate_json(response.model_dump_json()) == response


def test_series_response_round_trips_with_gaps_between_dates() -> None:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "points": [
                {
                    "valid_date": "2026-03-12",
                    "value": 2.61,
                    "version_id": 7,
                    "origin": "published",
                    "quality": {"status": "passed", "flags": []},
                },
                {
                    "valid_date": "2026-03-14",
                    "value": 2.7,
                    "version_id": 9,
                    "origin": "published",
                    "quality": {"status": "warn", "flags": []},
                },
            ],
        },
        "meta": {"as_of": "2026-03-15T09:00:00Z", "source_attribution": "Source: ECB statistics"},
    }

    response = v1.SeriesObservationsResponse.model_validate(body)

    assert [point.valid_date.day for point in response.data.points] == [12, 14]
    assert v1.SeriesObservationsResponse.model_validate_json(response.model_dump_json()) == response


def test_value_versions_response_round_trips() -> None:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "valid_date": "2026-03-12",
            "versions": [
                {
                    "version_id": 4711,
                    "value": 2.61,
                    "known_from": "2026-03-13T08:00:00Z",
                    "known_to": "2026-03-14T08:00:00Z",
                    "source_id": "ecb",
                    "run_id": "run-1",
                    "change_reason": "initial",
                    "normalization_version": "1",
                    "delivery_id": "4711",
                },
                {
                    "version_id": 4712,
                    "value": 2.7,
                    "known_from": "2026-03-14T08:00:00Z",
                    "known_to": None,
                    "source_id": "ecb",
                    "run_id": "run-2",
                    "change_reason": "revision",
                    "normalization_version": "1",
                    "delivery_id": None,
                },
            ],
        },
        "meta": {"as_of": "2026-03-15T09:00:00Z", "source_attribution": "Source: ECB statistics"},
    }

    response = v1.ValueVersionsResponse.model_validate(body)

    assert [version.change_reason for version in response.data.versions] == [
        v1.ChangeReason.INITIAL,
        v1.ChangeReason.REVISION,
    ]
    assert response.data.versions[1].known_to is None
    assert v1.ValueVersionsResponse.model_validate_json(response.model_dump_json()) == response


def test_curve_changes_round_trip() -> None:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_from": "2026-03-12",
            "valid_to": "2026-03-14",
            "changes": [
                {
                    "valid_date": "2026-03-12",
                    "maturity": "10Y",
                    "old_value": 2.61,
                    "new_value": 2.7,
                    "change_reason": "correction",
                    "source_id": "ecb",
                    "known_from": "2026-03-13T08:00:00Z",
                },
                {
                    "valid_date": "2026-03-13",
                    "maturity": "3M",
                    "old_value": None,
                    "new_value": 1.1,
                    "change_reason": "initial",
                    "source_id": None,
                    "known_from": "2026-03-13T08:00:00Z",
                },
            ],
        },
        "meta": {
            "since": "2026-03-12T08:00:00Z",
            "as_of": "2026-03-13T08:00:00Z",
            "source_attribution": "Source: ECB statistics",
        },
    }

    response = v1.CurveChangesResponse.model_validate(body)

    assert [change.old_value for change in response.data.changes] == [2.61, None]
    assert response.data.changes[0].change_reason is v1.ChangeReason.CORRECTION
    assert response.meta.since < response.meta.as_of
    assert v1.CurveChangesResponse.model_validate_json(response.model_dump_json()) == response


def test_quality_days_response_round_trips() -> None:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_from": "2026-10-05",
            "valid_to": "2026-10-08",
            "days": [
                {
                    "valid_date": "2026-10-07",
                    "status": "warn",
                    "run_id": "check-quality-ecb-aaa-spot-sim-2026-10-07",
                    "checked_as_of": "2026-10-08T06:00:00Z",
                    "rules": [{"rule": "missing-maturity", "outcome": "warn", "finding_count": 2}],
                    "findings": [
                        {
                            "rule": "missing-maturity",
                            "severity": "warn",
                            "maturity": "10Y",
                            "version_id": None,
                            "value": None,
                            "explanation": "No published value for this maturity.",
                            "evidence": "10Y missing on 2026-10-07",
                        }
                    ],
                }
            ],
        },
        "meta": {"as_of": "2026-10-08T06:00:00Z", "source_attribution": "Source: ECB statistics"},
    }

    response = v1.QualityDaysResponse.model_validate(body)

    assert response.data.days[0].status is v1.QualityStatus.WARN
    assert v1.QualityDaysResponse.model_validate_json(response.model_dump_json()) == response


def catalogue_response() -> dict[str, Any]:
    return {
        "data": [
            {
                "curve_id": "ecb-aaa-spot",
                "label": "ECB euro area AAA spot",
                "source_id": "ecb",
                "area": "Euro area",
                "attribution": "Source: ECB statistics",
                "rate_type": "spot",
                "compounding": "continuous",
                "unit": "percent",
                "source_model": "Svensson",
                "simulated": False,
                "maturities": [
                    {"maturity": "3M", "months": 3},
                    {"maturity": "10Y", "months": 120},
                ],
            }
        ]
    }


def test_curves_response_round_trips() -> None:
    response = v1.CurvesResponse.model_validate(catalogue_response())

    assert v1.CurvesResponse.model_validate_json(response.model_dump_json()) == response
    assert set(v1.CurveDefinition.model_fields) == {
        "curve_id",
        "label",
        "source_id",
        "area",
        "attribution",
        "rate_type",
        "compounding",
        "unit",
        "source_model",
        "simulated",
        "maturities",
    }


def test_curve_definition_rejects_maturities_out_of_grid_order() -> None:
    body = catalogue_response()
    body["data"][0]["maturities"] = [
        {"maturity": "10Y", "months": 120},
        {"maturity": "3M", "months": 3},
    ]

    with pytest.raises(ValidationError):
        v1.CurvesResponse.model_validate(body)


def test_curve_definition_rejects_an_unknown_rate_type() -> None:
    body = catalogue_response()
    body["data"][0]["rate_type"] = "bogus"

    with pytest.raises(ValidationError):
        v1.CurvesResponse.model_validate(body)


def measures_response(**meta_overrides: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "as_of": "2026-03-13T09:00:00Z",
        "method_version": "1",
        "source_attribution": "Source: ECB statistics",
    }
    return {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_from": "2026-03-12",
            "valid_to": "2026-03-12",
            "points": [
                {
                    "valid_date": "2026-03-12",
                    "spread_2y_10y": 66.0,
                    "spread_3m_10y": None,
                    "curvature_2y_5y_10y": None,
                    "inverted": False,
                    "inputs": [
                        {"maturity": "2Y", "value": 1.98, "version_id": 3, "status": "passed"},
                        {"maturity": "10Y", "value": 2.64, "version_id": 7, "status": "warn"},
                    ],
                    "missing": ["3M", "5Y"],
                    "quality": {"status": "warn", "flagged": ["10Y"]},
                }
            ],
        },
        "meta": meta_overrides or meta,
    }


def test_an_access_measures_response_round_trips_json() -> None:
    response = v1.MeasuresResponse.model_validate(measures_response())

    assert response.data.points[0].spread_2y_10y == 66.0
    assert response.data.points[0].inputs[1].status == v1.QualityStatus.WARN
    assert v1.MeasuresResponse.model_validate_json(response.model_dump_json()) == response


def test_access_measures_meta_requires_source_attribution() -> None:
    body = measures_response()
    del body["meta"]["source_attribution"]

    with pytest.raises(ValidationError):
        v1.MeasuresResponse.model_validate(body)


def test_grid_maturity_accepts_fractional_months() -> None:
    assert v1.GridMaturity(maturity="1.5M", months=1.5).months == 1.5

    with pytest.raises(ValidationError):
        v1.GridMaturity(maturity="1M", months=0)


def test_curve_point_accepts_fractional_months() -> None:
    point = v1.CurvePoint(
        maturity="1.5M", months=1.5, value=4.3, version_id=1, origin="published", quality=None
    )

    assert point.months == 1.5


def test_curves_response_accepts_increasing_fractional_months() -> None:
    body = catalogue_response()
    body["data"][0]["maturities"] = [
        {"maturity": "1M", "months": 1},
        {"maturity": "1.5M", "months": 1.5},
        {"maturity": "2M", "months": 2},
    ]

    curves = v1.CurvesResponse.model_validate(body)

    assert [maturity.months for maturity in curves.data[0].maturities] == [1, 1.5, 2]


def test_curves_response_rejects_equal_months() -> None:
    body = catalogue_response()
    body["data"][0]["maturities"] = [
        {"maturity": "1M", "months": 1},
        {"maturity": "1.5M", "months": 1},
    ]

    with pytest.raises(ValidationError, match="ordered by months"):
        v1.CurvesResponse.model_validate(body)
