from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from contracts.persistence.v1 import (
    MAX_BATCH_SIZE,
    ChangeReason,
    Compounding,
    CurveChangesResponse,
    CurveDefinition,
    CurveObservationsResponse,
    CurvePoint,
    ObservationVersion,
    Origin,
    RateType,
    RecordVersionsRequest,
    RecordVersionsResponse,
    SeriesObservationsResponse,
    SeriesPoint,
    ValueChange,
    ValueVersion,
    ValueVersionsResponse,
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
                {"maturity": "3M", "months": 3, "value": None, "version_id": None},
                {"maturity": "10Y", "months": 120, "value": 2.61, "version_id": 7},
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
    point = CurvePoint(maturity="10Y", months=120, value=2.61, version_id=7)

    assert '"value":2.61' in point.model_dump_json()


def test_curve_point_version_id_is_null_exactly_when_value_is_null() -> None:
    with pytest.raises(ValidationError, match="version_id"):
        CurvePoint(maturity="10Y", months=120, value=2.61, version_id=None)
    with pytest.raises(ValidationError, match="version_id"):
        CurvePoint(maturity="3M", months=3, value=None, version_id=7)
    assert CurvePoint(maturity="3M", months=3, value=None, version_id=None).version_id is None


def series_response(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "points": [
                {"valid_date": "2026-03-12", "value": 2.61, "version_id": 7},
                {"valid_date": "2026-03-14", "value": 2.7, "version_id": 9},
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


def value_versions_response(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "valid_date": "2026-03-12",
            "versions": [
                {
                    "version_id": 1,
                    "value": 2.61,
                    "known_from": "2026-03-12T18:00:00Z",
                    "known_to": "2026-03-13T18:00:00Z",
                    "source_id": "ecb",
                    "run_id": "ingestion-ecb-2026-03-12",
                    "change_reason": "initial",
                    "normalization_version": "1",
                    "delivery_id": None,
                },
                {
                    "version_id": 2,
                    "value": 2.7,
                    "known_from": "2026-03-13T18:00:00Z",
                    "known_to": None,
                    "source_id": "ecb",
                    "run_id": "ingestion-ecb-2026-03-13",
                    "change_reason": "revision",
                    "normalization_version": None,
                    "delivery_id": "4711",
                },
            ],
        },
        "meta": {"as_of": "2026-03-14T09:00:00Z"},
    }
    return body | overrides


def test_value_versions_response_round_trips() -> None:
    response = ValueVersionsResponse.model_validate(value_versions_response())

    assert [version.value for version in response.data.versions] == [2.61, 2.7]
    assert response.data.versions[0].known_to == response.data.versions[1].known_from
    assert response.data.versions[1].known_to is None
    assert response.data.versions[1].change_reason is ChangeReason.REVISION
    assert ValueVersionsResponse.model_validate_json(response.model_dump_json()) == response


def test_value_version_rejects_a_naive_known_from() -> None:
    with pytest.raises(ValidationError, match="known_from"):
        ValueVersion.model_validate(
            value_versions_response()["data"]["versions"][0] | {"known_from": "2026-03-12T18:00:00"}
        )


def changes_response(**overrides: Any) -> dict[str, Any]:
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
                    "known_from": "2026-03-13T18:00:00Z",
                },
            ],
        },
        "meta": {
            "since": "2026-03-12T18:00:00Z",
            "as_of": "2026-03-13T18:00:00Z",
        },
    }
    return body | overrides


def test_curve_changes_round_trip() -> None:
    response = CurveChangesResponse.model_validate(changes_response())

    assert response.data.valid_from == date(2026, 3, 12)
    assert response.data.changes[0].old_value == 2.61
    assert response.data.changes[0].change_reason is ChangeReason.CORRECTION
    assert response.meta.since < response.meta.as_of
    assert CurveChangesResponse.model_validate_json(response.model_dump_json()) == response


def test_value_change_allows_a_missing_old_value() -> None:
    change = ValueChange.model_validate(
        changes_response()["data"]["changes"][0] | {"old_value": None, "change_reason": "initial"}
    )

    assert change.old_value is None
    assert change.new_value == 2.7


def test_value_change_rejects_a_non_finite_new_value() -> None:
    with pytest.raises(ValidationError, match="new_value"):
        ValueChange.model_validate(changes_response()["data"]["changes"][0] | {"new_value": "NaN"})


def definition(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "curve_id": "ecb-aaa-spot",
        "label": "ECB euro area AAA spot",
        "source_id": "ecb",
        "area": "Euro area",
        "attribution": "Source: ECB statistics",
        "rate_type": "spot",
        "compounding": "continuous",
        "unit": "percent",
        "source_model": "Svensson (ECB)",
        "simulated": False,
        "maturities": [
            {"maturity": "3M", "months": 3},
            {"maturity": "10Y", "months": 120},
        ],
    }
    return fields | overrides


def test_parses_a_curve_definition_from_json_types() -> None:
    curve = CurveDefinition.model_validate(definition())

    assert curve.rate_type is RateType.SPOT
    assert curve.compounding is Compounding.CONTINUOUS
    assert curve.simulated is False
    assert curve.maturities[1].months == 120


def test_curve_definition_source_model_may_be_null() -> None:
    curve = CurveDefinition.model_validate(definition(source_model=None))

    assert curve.source_model is None


def test_curve_definition_rejects_maturities_out_of_grid_order() -> None:
    maturities = [{"maturity": "10Y", "months": 120}, {"maturity": "3M", "months": 3}]

    with pytest.raises(ValidationError, match="ordered by months"):
        CurveDefinition.model_validate(definition(maturities=maturities))


def test_curve_definition_rejects_an_unknown_rate_type() -> None:
    with pytest.raises(ValidationError):
        CurveDefinition.model_validate(definition(rate_type="zero"))


def test_curve_definition_requires_an_attribution() -> None:
    with pytest.raises(ValidationError):
        CurveDefinition.model_validate(definition(attribution=""))
