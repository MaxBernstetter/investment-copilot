from typing import Any

from contracts.access import v1


def curve_response(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "valid_date": "2026-03-12",
            "points": [
                {"maturity": "3M", "months": 3, "value": None},
                {"maturity": "10Y", "months": 120, "value": 2.61},
            ],
        },
        "meta": {"as_of": "2026-03-13T09:00:00Z"},
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
                {"valid_date": "2026-03-12", "value": 2.61},
                {"valid_date": "2026-03-14", "value": 2.7},
            ],
        },
        "meta": {"as_of": "2026-03-15T09:00:00Z"},
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
        "meta": {"as_of": "2026-03-15T09:00:00Z"},
    }

    response = v1.ValueVersionsResponse.model_validate(body)

    assert [version.change_reason for version in response.data.versions] == [
        v1.ChangeReason.INITIAL,
        v1.ChangeReason.REVISION,
    ]
    assert response.data.versions[1].known_to is None
    assert v1.ValueVersionsResponse.model_validate_json(response.model_dump_json()) == response
