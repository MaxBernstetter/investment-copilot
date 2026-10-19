from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from contracts.persistence.v1 import (
    MAX_BATCH_SIZE,
    ChangeReason,
    CurveObservationsResponse,
    CurvePoint,
    ObservationVersion,
    Origin,
    RecordVersionsRequest,
    RecordVersionsResponse,
    SeriesObservationsResponse,
    SeriesPoint,
)


def published(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "curve_id": "ecb-aaa-spot",
        "maturity": "10Y",
        "valid_date": "2026-03-12",
        "value": 2.61,
        "origin": "published",
        "source_id": "ecb",
        "run_id": "ingestion-ecb-2026-03-12",
        "change_reason": "initial",
    }
    return fields | overrides


def test_parses_a_published_observation_from_json_types() -> None:
    observation = ObservationVersion.model_validate(published(value="2.61"))

    assert observation.valid_date == date(2026, 3, 12)
    assert observation.value == Decimal("2.61")
    assert observation.origin is Origin.PUBLISHED
    assert observation.change_reason is ChangeReason.INITIAL
    assert observation.method_version is None
    assert observation.normalization_version is None


def test_carries_the_normalization_version_of_a_published_observation() -> None:
    observation = ObservationVersion.model_validate(published(normalization_version="1"))

    assert observation.normalization_version == "1"


def test_derived_observation_requires_a_method_version() -> None:
    with pytest.raises(ValidationError, match="method_version"):
        ObservationVersion.model_validate(published(origin="derived"))


def test_published_observation_rejects_a_method_version() -> None:
    with pytest.raises(ValidationError, match="method_version"):
        ObservationVersion.model_validate(published(method_version="nss-1"))


def test_derived_observation_with_method_version_is_valid() -> None:
    observation = ObservationVersion.model_validate(
        published(origin="derived", method_version="nss-1", source_id=None)
    )

    assert observation.method_version == "nss-1"


@pytest.mark.parametrize("maturity", ["3M", "10Y", "1Y6M", "1W"])
def test_accepts_tenor_codes(maturity: str) -> None:
    assert ObservationVersion.model_validate(published(maturity=maturity)).maturity == maturity


@pytest.mark.parametrize("maturity", ["", "10", "Y", "0Y", "10y", "10 Y"])
def test_rejects_malformed_maturities(maturity: str) -> None:
    with pytest.raises(ValidationError, match="maturity"):
        ObservationVersion.model_validate(published(maturity=maturity))


@pytest.mark.parametrize("value", ["NaN", "Infinity"])
def test_rejects_non_finite_values(value: str) -> None:
    with pytest.raises(ValidationError, match="value"):
        ObservationVersion.model_validate(published(value=value))


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="known_from"):
        ObservationVersion.model_validate(published(known_from="2026-03-12T18:00:00Z"))


def test_delivery_id_is_optional_provenance() -> None:
    without = ObservationVersion.model_validate(published())
    linked = ObservationVersion.model_validate(published(delivery_id="4711"))

    assert without.delivery_id is None
    assert linked.delivery_id == "4711"


@pytest.mark.parametrize("delivery_id", ["", "x" * 65])
def test_rejects_an_empty_or_too_long_delivery_id(delivery_id: str) -> None:
    with pytest.raises(ValidationError, match="delivery_id"):
        ObservationVersion.model_validate(published(delivery_id=delivery_id))


def test_request_needs_at_least_one_observation() -> None:
    with pytest.raises(ValidationError, match="observations"):
        RecordVersionsRequest.model_validate({"observations": []})


def test_request_is_bounded() -> None:
    too_many = [published()] * (MAX_BATCH_SIZE + 1)

    with pytest.raises(ValidationError, match="observations"):
        RecordVersionsRequest.model_validate({"observations": too_many})


def test_response_requires_a_timezone_aware_knowledge_time() -> None:
    with pytest.raises(ValidationError, match="known_from"):
        RecordVersionsResponse.model_validate(
            {"recorded_count": 1, "known_from": "2026-03-12T18:00:00"}
        )


def test_response_reports_unchanged_observations() -> None:
    response = RecordVersionsResponse.model_validate(
        {"recorded_count": 1, "unchanged_count": 9, "known_from": "2026-03-12T18:00:00Z"}
    )

    assert (response.recorded_count, response.unchanged_count) == (1, 9)


def test_response_without_unchanged_count_reports_none() -> None:
    response = RecordVersionsResponse.model_validate(
        {"recorded_count": 1, "known_from": "2026-03-12T18:00:00Z"}
    )

    assert response.unchanged_count == 0


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
    response = CurveObservationsResponse.model_validate(curve_response())

    assert response.data.points[0].value is None
    assert response.data.points[1].value == 2.61
    assert CurveObservationsResponse.model_validate_json(response.model_dump_json()) == response


def test_curve_response_requires_an_aware_as_of() -> None:
    with pytest.raises(ValidationError, match="as_of"):
        CurveObservationsResponse.model_validate(
            curve_response(meta={"as_of": "2026-03-13T09:00:00"})
        )


def test_curve_point_value_is_a_json_number() -> None:
    point = CurvePoint(maturity="10Y", months=120, value=2.61)

    assert '"value":2.61' in point.model_dump_json()


def series_response(**overrides: Any) -> dict[str, Any]:
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
    return body | overrides


def test_series_response_round_trips_with_gaps_between_dates() -> None:
    response = SeriesObservationsResponse.model_validate(series_response())

    assert [point.valid_date for point in response.data.points] == [
        date(2026, 3, 12),
        date(2026, 3, 14),
    ]
    assert SeriesObservationsResponse.model_validate_json(response.model_dump_json()) == response


def test_series_point_rejects_a_non_finite_value() -> None:
    with pytest.raises(ValidationError, match="value"):
        SeriesPoint.model_validate({"valid_date": "2026-03-12", "value": "NaN"})
