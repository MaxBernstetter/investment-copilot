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
