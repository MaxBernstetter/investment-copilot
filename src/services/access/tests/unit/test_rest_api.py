import logging
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext
from starlette.types import Receive, Scope, Send

from access.application.catalogue import CachedCatalogue
from access.domain.catalogue import CurveDefinition, GridMaturity
from access.domain.changes import CurveChanges, ValueChange
from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
    ProcessingUnavailableError,
)
from access.domain.measures import (
    CurveMeasures,
    MeasureInput,
    MeasurePoint,
    MeasureQuality,
    MeasuresUnavailableError,
)
from access.domain.quality import (
    QualityFlag,
    QualityStatus,
    Severity,
    ValueQuality,
)
from access.domain.quality_days import QualityDay, QualityDays, QualityFinding, RuleOutcome
from access.domain.series import Series, SeriesPoint
from access.domain.versions import ChangeReason, ValueVersion, ValueVersions
from access.facade.rest.app import Services, create_app

FRONTEND_ORIGIN = "http://localhost:5174"
PASSED_QUALITY = {"status": "passed", "flags": []}
UNCHECKED_QUALITY = {"status": "unchecked", "flags": []}
CURVE_PATH = "/v1/curves/ecb-aaa-spot/observations"
SERIES_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations"
VERSIONS_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations/2026-03-12/versions"
CHANGES_PATH = "/v1/curves/ecb-aaa-spot/changes"
QUALITY_PATH = "/v1/curves/ecb-aaa-spot/quality"
MEASURES_PATH = "/v1/curves/ecb-aaa-spot/measures"
MEASURES_UNAVAILABLE = "The measures service is not reachable; try again later."
SINCE = datetime(2026, 3, 12, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
AS_OF = datetime(2026, 3, 13, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))


class FakeCurveReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date | None, datetime | None]] = []
        self.series_calls: list[tuple[str, str, date | None, date | None, datetime | None]] = []
        self.versions_calls: list[tuple[str, str, date, datetime | None]] = []
        self.changes_calls: list[tuple[str, date, date, datetime, datetime | None]] = []
        self.error: Exception | None = None
        self.value: float = 2.61

    async def changes(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        since: datetime,
        as_of: datetime | None,
    ) -> CurveChanges:
        self.changes_calls.append((curve_id, valid_from, valid_to, since, as_of))
        if self.error is not None:
            raise self.error
        return CurveChanges(
            curve_id=curve_id,
            valid_from=valid_from,
            valid_to=valid_to,
            since=SINCE.astimezone(UTC),
            as_of=AS_OF,
            changes=(
                ValueChange(
                    valid_date=date(2026, 3, 12),
                    maturity="10Y",
                    old_value=2.61,
                    new_value=2.7,
                    change_reason=ChangeReason.CORRECTION,
                    source_id="ecb",
                    known_from=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
                ),
            ),
        )

    async def value_versions(
        self, curve_id: str, maturity: str, valid_date: date, as_of: datetime | None
    ) -> ValueVersions:
        self.versions_calls.append((curve_id, maturity, valid_date, as_of))
        if self.error is not None:
            raise self.error
        return ValueVersions(
            curve_id=curve_id,
            maturity=maturity,
            valid_date=valid_date,
            as_of=AS_OF,
            versions=(
                ValueVersion(
                    version_id=4711,
                    value=2.61,
                    known_from=datetime(2026, 3, 13, 8, 0, tzinfo=UTC),
                    known_to=None,
                    source_id="ecb",
                    run_id="run-1",
                    change_reason=ChangeReason.INITIAL,
                    normalization_version="1",
                    delivery_id="4711",
                ),
            ),
        )

    async def series_as_of(
        self,
        curve_id: str,
        maturity: str,
        valid_from: date | None,
        valid_to: date | None,
        as_of: datetime | None,
    ) -> Series:
        self.series_calls.append((curve_id, maturity, valid_from, valid_to, as_of))
        if self.error is not None:
            raise self.error
        return Series(
            curve_id=curve_id,
            maturity=maturity,
            as_of=AS_OF,
            points=(SeriesPoint(valid_date=date(2026, 3, 12), value=self.value, version_id=7),),
        )

    async def curve_as_of(
        self, curve_id: str, valid_date: date | None, as_of: datetime | None
    ) -> CurveAsOf:
        self.calls.append((curve_id, valid_date, as_of))
        if self.error is not None:
            raise self.error
        return CurveAsOf(
            curve_id=curve_id,
            valid_date=date(2026, 3, 12),
            as_of=AS_OF,
            points=(
                CurvePoint(maturity="3M", months=3, value=None, version_id=None),
                CurvePoint(maturity="10Y", months=120, value=self.value, version_id=7),
            ),
        )


class FakeQualityReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date, str | None, datetime]] = []
        self.days_calls: list[tuple[str, date, date, datetime | None]] = []
        self.known: dict[int, ValueQuality] | None = {
            7: ValueQuality(status=QualityStatus.PASSED, flags=())
        }
        self.unavailable = False
        self.days_error: Exception | None = None
        self.days_result = QualityDays(
            curve_id="ecb-aaa-spot",
            valid_from=date(2026, 3, 12),
            valid_to=date(2026, 3, 14),
            as_of=AS_OF,
            days=(
                QualityDay(
                    valid_date=date(2026, 3, 12),
                    status=QualityStatus.WARN,
                    run_id="check-1",
                    checked_as_of=AS_OF.astimezone(UTC),
                    rules=(
                        RuleOutcome(
                            rule="range",
                            outcome=QualityStatus.WARN,
                            finding_count=1,
                        ),
                    ),
                    findings=(
                        QualityFinding(
                            rule="range",
                            severity=Severity.WARN,
                            maturity="10Y",
                            version_id=7,
                            value=26.4,
                            explanation="Yield is outside the plausible range",
                            evidence="26.4 % is above 15 %",
                        ),
                    ),
                ),
            ),
        )

    async def value_quality(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        maturity: str | None,
        as_of: datetime,
    ) -> dict[int, ValueQuality] | None:
        self.calls.append((curve_id, valid_from, valid_to, maturity, as_of))
        if self.unavailable:
            return None
        return self.known

    async def quality_days(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> QualityDays:
        self.days_calls.append((curve_id, valid_from, valid_to, as_of))
        if self.days_error is not None:
            raise self.days_error
        return replace(self.days_result, curve_id=curve_id)


class FakeCatalogueReader:
    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None
        self.curves_result: tuple[CurveDefinition, ...] = (
            CurveDefinition(
                curve_id="ecb-aaa-spot",
                label="ECB euro area AAA spot",
                source_id="ecb",
                area="Euro area",
                attribution="Source: ECB statistics",
                rate_type="spot",
                compounding="continuous",
                unit="percent",
                source_model="Svensson",
                simulated=False,
                maturities=(GridMaturity("3M", 3), GridMaturity("10Y", 120)),
            ),
            CurveDefinition(
                curve_id="ecb-aaa-spot-sim",
                label="ECB euro area AAA spot (simulated)",
                source_id="scenario",
                area="Euro area",
                attribution="Simulated scenario based on ECB statistics",
                rate_type="spot",
                compounding="continuous",
                unit="percent",
                source_model="Svensson",
                simulated=True,
                maturities=(GridMaturity("3M", 3), GridMaturity("10Y", 120)),
            ),
        )

    async def curves(self) -> tuple[CurveDefinition, ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.curves_result


def measure_point(input_status: QualityStatus = QualityStatus.PASSED) -> MeasurePoint:
    return MeasurePoint(
        valid_date=date(2026, 3, 12),
        spread_2y_10y=66.0,
        spread_3m_10y=None,
        curvature_2y_5y_10y=None,
        inverted=False,
        inputs=(
            MeasureInput("2Y", 1.98, 3, input_status),
            MeasureInput("10Y", 2.64, 7, input_status),
        ),
        missing=("3M", "5Y"),
        quality=MeasureQuality(status=input_status, flagged=()),
    )


class FakeMeasuresReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date, datetime | None]] = []
        self.error: Exception | None = None
        self.result = CurveMeasures(
            curve_id="ecb-aaa-spot",
            valid_from=date(2026, 3, 12),
            valid_to=date(2026, 3, 12),
            as_of=AS_OF.astimezone(UTC),
            method_version="1",
            points=(measure_point(),),
        )

    async def measures(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> CurveMeasures:
        self.calls.append((curve_id, valid_from, valid_to, as_of))
        if self.error is not None:
            raise self.error
        return replace(self.result, curve_id=curve_id, valid_from=valid_from, valid_to=valid_to)


class FakeServices:
    def __init__(self) -> None:
        self.ready = True
        self.curves = FakeCurveReader()
        self.quality = FakeQualityReader()
        self.catalogue_reader = FakeCatalogueReader()
        self.measures = FakeMeasuresReader()

    async def is_ready(self) -> bool:
        return self.ready

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Services]:
        yield Services(
            self.is_ready,
            self.curves,
            self.quality,
            CachedCatalogue(self.catalogue_reader, ttl_seconds=60),
            self.measures,
        )


@pytest.fixture
def services() -> FakeServices:
    return FakeServices()


@pytest.fixture
def client(services: FakeServices) -> Iterator[TestClient]:
    with TestClient(create_app(services.open, cors_origins=[FRONTEND_ORIGIN])) as client:
        yield client


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_persistence_is_ready(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_when_persistence_is_not(client: TestClient, services: FakeServices) -> None:
    services.ready = False

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/ready",
        headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_cors_ignores_other_origins(client: TestClient) -> None:
    response = client.options(
        "/ready",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_returns_the_curve_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(CURVE_PATH)

    assert response.status_code == 200
    assert response.json() == {
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
                    "quality": PASSED_QUALITY,
                },
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z", "source_attribution": "Source: ECB statistics"},
    }


def test_passes_valid_date_and_as_of_to_persistence(
    client: TestClient, services: FakeServices
) -> None:
    client.get(CURVE_PATH, params={"valid_date": "2026-03-12", "as_of": AS_OF.isoformat()})

    assert services.curves.calls == [("ecb-aaa-spot", date(2026, 3, 12), AS_OF)]


def test_without_parameters_persistence_gets_none(
    client: TestClient, services: FakeServices
) -> None:
    client.get(CURVE_PATH)

    assert services.curves.calls == [("ecb-aaa-spot", None, None)]


def test_not_found_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = CurveNotFoundError("no curve named ecb-aaa-spot")

    response = client.get(CURVE_PATH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not found",
        "status": 404,
        "detail": "no curve named ecb-aaa-spot",
    }


def test_invalid_query_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = InvalidCurveQueryError("valid_date is outside the window")

    response = client.get(CURVE_PATH)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    assert response.json()["detail"] == "valid_date is outside the window"


def test_unavailable_persistence_is_a_503_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = PersistenceUnavailableError()

    response = client.get(CURVE_PATH)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Service unavailable",
        "status": 503,
        "detail": "The curve store is not reachable; try again later.",
    }


def test_bad_parameters_are_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(CURVE_PATH, params={"valid_date": "abc"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["title"] == "Invalid request"
    assert services.curves.calls == []


def test_naive_as_of_is_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(CURVE_PATH, params={"as_of": "2026-03-13T09:00:00"})

    assert response.status_code == 422
    assert services.curves.calls == []


def test_only_get_is_allowed(client: TestClient) -> None:
    response = client.post(CURVE_PATH)

    assert response.status_code == 405


def test_returns_the_series_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(SERIES_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "points": [
                {
                    "valid_date": "2026-03-12",
                    "value": 2.61,
                    "version_id": 7,
                    "origin": "published",
                    "quality": PASSED_QUALITY,
                }
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z", "source_attribution": "Source: ECB statistics"},
    }


def test_passes_the_range_and_as_of_of_a_series_to_persistence(
    client: TestClient, services: FakeServices
) -> None:
    client.get(
        SERIES_PATH,
        params={"from": "2026-03-01", "to": "2026-03-12", "as_of": AS_OF.isoformat()},
    )

    assert services.curves.series_calls == [
        ("ecb-aaa-spot", "10Y", date(2026, 3, 1), date(2026, 3, 12), AS_OF)
    ]


def test_series_without_parameters_persistence_gets_none(
    client: TestClient, services: FakeServices
) -> None:
    client.get(SERIES_PATH)

    assert services.curves.series_calls == [("ecb-aaa-spot", "10Y", None, None, None)]


def test_series_not_found_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = CurveNotFoundError("maturity 4Y is not on the grid")

    response = client.get(SERIES_PATH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"
    assert response.json()["detail"] == "maturity 4Y is not on the grid"


def test_series_invalid_range_is_passed_through_as_a_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = InvalidCurveQueryError("from is after to")

    response = client.get(SERIES_PATH)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    assert response.json()["detail"] == "from is after to"


def test_series_unavailable_persistence_is_a_503_problem(
    client: TestClient, services: FakeServices
) -> None:
    services.curves.error = PersistenceUnavailableError()

    response = client.get(SERIES_PATH)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Service unavailable"


def test_series_bad_parameters_are_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(SERIES_PATH, params={"from": "abc"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    assert services.curves.series_calls == []


def test_series_naive_as_of_is_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(SERIES_PATH, params={"as_of": "2026-03-13T09:00:00"})

    assert response.status_code == 422
    assert services.curves.series_calls == []


CATALOGUE_PATH = "/v1/curves"


def test_returns_the_catalogue_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(CATALOGUE_PATH)

    assert response.status_code == 200
    assert response.json() == {
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
            },
            {
                "curve_id": "ecb-aaa-spot-sim",
                "label": "ECB euro area AAA spot (simulated)",
                "source_id": "scenario",
                "area": "Euro area",
                "attribution": "Simulated scenario based on ECB statistics",
                "rate_type": "spot",
                "compounding": "continuous",
                "unit": "percent",
                "source_model": "Svensson",
                "simulated": True,
                "maturities": [
                    {"maturity": "3M", "months": 3},
                    {"maturity": "10Y", "months": 120},
                ],
            },
        ]
    }


def test_catalogue_carries_an_etag_and_reference_cache_control(client: TestClient) -> None:
    first = client.get(CATALOGUE_PATH)
    assert first.status_code == 200
    assert re.fullmatch(r'"[0-9a-f]{32}"', first.headers["etag"])
    assert first.headers["cache-control"] == "public, max-age=300"

    second = client.get(CATALOGUE_PATH, headers={"If-None-Match": first.headers["etag"]})

    assert second.status_code == 304
    assert second.headers["cache-control"] == "public, max-age=300"


def test_catalogue_unavailable_is_a_503_problem(client: TestClient, services: FakeServices) -> None:
    services.catalogue_reader.error = PersistenceUnavailableError()

    response = client.get(CATALOGUE_PATH)

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Service unavailable"


@pytest.mark.parametrize(
    "path",
    [
        "/v1/curves/ecb-aaa-spot/observations",
        "/v1/curves/ecb-aaa-spot/maturities/10Y/observations",
        "/v1/curves/ecb-aaa-spot/maturities/10Y/observations/2026-03-12/versions",
        "/v1/curves/ecb-aaa-spot/changes",
        "/v1/curves/ecb-aaa-spot/quality",
    ],
)
def test_attribution_comes_from_the_catalogue(
    client: TestClient, services: FakeServices, path: str
) -> None:
    services.catalogue_reader.curves_result = tuple(
        replace(curve, attribution="Source: test catalogue")
        if curve.curve_id == "ecb-aaa-spot"
        else curve
        for curve in services.catalogue_reader.curves_result
    )
    params = {"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()}

    response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.json()["meta"]["source_attribution"] == "Source: test catalogue"


def test_the_catalogue_is_read_once_for_many_requests(
    client: TestClient, services: FakeServices
) -> None:
    client.get(CURVE_PATH)
    client.get(SERIES_PATH)

    assert services.catalogue_reader.calls == 1


def test_curve_response_carries_an_etag(client: TestClient) -> None:
    response = client.get(CURVE_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-cache"
    assert re.fullmatch(r'"[0-9a-f]{32}"', response.headers["etag"])


def test_the_same_answer_has_the_same_etag(client: TestClient) -> None:
    first = client.get(CURVE_PATH)
    second = client.get(CURVE_PATH)

    assert first.headers["etag"] == second.headers["etag"]


def test_if_none_match_with_the_current_etag_is_not_modified(client: TestClient) -> None:
    etag = client.get(CURVE_PATH).headers["etag"]

    response = client.get(CURVE_PATH, headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "if_none_match",
    ['"0123"', '"0123", "4567"', 'W/"0123"'],
)
def test_if_none_match_with_another_etag_returns_the_body(
    client: TestClient, if_none_match: str
) -> None:
    response = client.get(CURVE_PATH, headers={"If-None-Match": if_none_match})

    assert response.status_code == 200
    assert response.json()["data"]["curve_id"] == "ecb-aaa-spot"


def test_if_none_match_accepts_a_list_and_weak_tags(client: TestClient) -> None:
    etag = client.get(CURVE_PATH).headers["etag"]

    listed = client.get(CURVE_PATH, headers={"If-None-Match": f'"0123", {etag}'})
    weak = client.get(CURVE_PATH, headers={"If-None-Match": f"W/{etag}"})
    wildcard = client.get(CURVE_PATH, headers={"If-None-Match": "*"})

    assert listed.status_code == 304
    assert weak.status_code == 304
    assert wildcard.status_code == 304


def test_series_response_carries_an_etag(client: TestClient) -> None:
    response = client.get(SERIES_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert re.fullmatch(r'"[0-9a-f]{32}"', response.headers["etag"])

    etag = response.headers["etag"]
    conditional = client.get(SERIES_PATH, headers={"If-None-Match": etag})
    assert conditional.status_code == 304
    assert conditional.content == b""


def test_errors_carry_no_etag(client: TestClient, services: FakeServices) -> None:
    services.curves.error = CurveNotFoundError("no curve named ecb-aaa-spot")
    assert "etag" not in client.get(CURVE_PATH).headers

    services.curves.error = PersistenceUnavailableError()
    assert "etag" not in client.get(SERIES_PATH).headers

    services.curves.error = None
    assert "etag" not in client.get(CURVE_PATH, params={"valid_date": "abc"}).headers


def test_the_body_is_unchanged(client: TestClient) -> None:
    response = client.get(CURVE_PATH)

    assert response.json() == {
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
                    "quality": PASSED_QUALITY,
                },
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z", "source_attribution": "Source: ECB statistics"},
    }


IMMUTABLE = "public, max-age=31536000, immutable"


def test_a_settled_as_of_is_immutable(client: TestClient) -> None:
    curve = client.get(CURVE_PATH, params={"as_of": AS_OF.isoformat()})
    series = client.get(SERIES_PATH, params={"as_of": AS_OF.isoformat()})

    assert curve.headers["cache-control"] == IMMUTABLE
    assert series.headers["cache-control"] == IMMUTABLE


def test_no_as_of_must_be_revalidated(client: TestClient) -> None:
    assert client.get(CURVE_PATH).headers["cache-control"] == "no-cache"
    assert client.get(SERIES_PATH).headers["cache-control"] == "no-cache"


def test_an_as_of_after_the_horizon_must_be_revalidated(
    client: TestClient, services: FakeServices
) -> None:
    # The fake answers with AS_OF, which is earlier than the requested time: persistence
    # clamped the request to its knowledge horizon, so the answer may still change.
    later = AS_OF.replace(hour=12)

    curve = client.get(CURVE_PATH, params={"as_of": later.isoformat()})
    series = client.get(SERIES_PATH, params={"as_of": later.isoformat()})

    assert curve.headers["cache-control"] == "no-cache"
    assert series.headers["cache-control"] == "no-cache"


def test_not_modified_keeps_cache_control(client: TestClient) -> None:
    params = {"as_of": AS_OF.isoformat()}
    etag = client.get(CURVE_PATH, params=params).headers["etag"]

    response = client.get(CURVE_PATH, params=params, headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.headers["cache-control"] == IMMUTABLE


def test_the_same_instant_in_another_offset_is_settled(client: TestClient) -> None:
    in_utc = AS_OF.astimezone(ZoneInfo("UTC")).isoformat()

    response = client.get(CURVE_PATH, params={"as_of": in_utc})

    assert response.headers["cache-control"] == IMMUTABLE


def test_value_versions_envelope(client: TestClient, services: FakeServices) -> None:
    response = client.get(VERSIONS_PATH, params={"as_of": AS_OF.isoformat()})

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "curve_id": "ecb-aaa-spot",
            "maturity": "10Y",
            "valid_date": "2026-03-12",
            "versions": [
                {
                    "version_id": 4711,
                    "value": 2.61,
                    "known_from": "2026-03-13T08:00:00Z",
                    "known_to": None,
                    "source_id": "ecb",
                    "run_id": "run-1",
                    "change_reason": "initial",
                    "normalization_version": "1",
                    "delivery_id": "4711",
                }
            ],
        },
        "meta": {"as_of": "2026-03-13T08:00:00Z", "source_attribution": "Source: ECB statistics"},
    }
    assert services.curves.versions_calls == [("ecb-aaa-spot", "10Y", date(2026, 3, 12), AS_OF)]


def test_value_versions_not_found_is_404(client: TestClient, services: FakeServices) -> None:
    services.curves.error = CurveNotFoundError("maturity 4Y is not on the grid")

    response = client.get(VERSIONS_PATH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"
    assert response.json()["detail"] == "maturity 4Y is not on the grid"


def test_value_versions_bad_date_is_422(client: TestClient, services: FakeServices) -> None:
    response = client.get(VERSIONS_PATH.replace("2026-03-12", "12.03.2026"))

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Invalid request"
    assert services.curves.versions_calls == []


def test_value_versions_unavailable_is_503(client: TestClient, services: FakeServices) -> None:
    services.curves.error = PersistenceUnavailableError()

    response = client.get(VERSIONS_PATH)

    assert response.status_code == 503
    assert response.json()["title"] == "Service unavailable"


def test_value_versions_carry_an_etag(client: TestClient) -> None:
    response = client.get(VERSIONS_PATH)

    assert response.status_code == 200
    assert re.fullmatch(r'"[0-9a-f]{32}"', response.headers["etag"])

    conditional = client.get(VERSIONS_PATH, headers={"If-None-Match": response.headers["etag"]})
    assert conditional.status_code == 304
    assert conditional.content == b""


def test_settled_value_versions_are_immutable(client: TestClient) -> None:
    response = client.get(VERSIONS_PATH, params={"as_of": AS_OF.isoformat()})

    assert response.headers["cache-control"] == IMMUTABLE


def test_returns_the_changes_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(
        CHANGES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()},
    )

    assert response.status_code == 200
    assert response.json() == {
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
                }
            ],
        },
        "meta": {
            "since": "2026-03-12T08:00:00Z",
            "as_of": "2026-03-13T08:00:00Z",
            "source_attribution": "Source: ECB statistics",
        },
    }


def test_passes_range_since_and_as_of_to_persistence(
    client: TestClient, services: FakeServices
) -> None:
    client.get(
        CHANGES_PATH,
        params={
            "from": "2026-03-12",
            "to": "2026-03-14",
            "since": SINCE.isoformat(),
            "as_of": AS_OF.isoformat(),
        },
    )

    assert services.curves.changes_calls == [
        ("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), SINCE, AS_OF)
    ]


def test_settled_changes_are_immutable(client: TestClient) -> None:
    response = client.get(
        CHANGES_PATH,
        params={
            "from": "2026-03-12",
            "to": "2026-03-14",
            "since": SINCE.isoformat(),
            "as_of": AS_OF.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE


def test_changes_without_as_of_are_no_cache(client: TestClient, services: FakeServices) -> None:
    response = client.get(
        CHANGES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert services.curves.changes_calls[0][4] is None


def test_changes_missing_since_is_rejected_without_calling_persistence(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(CHANGES_PATH, params={"from": "2026-03-12", "to": "2026-03-14"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert services.curves.changes_calls == []


def test_points_carry_version_id_and_origin_published(client: TestClient) -> None:
    curve = client.get(CURVE_PATH).json()["data"]["points"]
    series = client.get(SERIES_PATH).json()["data"]["points"]

    assert [(point["version_id"], point["origin"]) for point in curve] == [
        (None, "published"),
        (7, "published"),
    ]
    assert [(point["version_id"], point["origin"]) for point in series] == [(7, "published")]


def test_values_are_returned_unmodified(client: TestClient, services: FakeServices) -> None:
    services.curves.value = 2.871234567890123

    curve = client.get(CURVE_PATH)
    series = client.get(SERIES_PATH)

    assert [point["value"] for point in curve.json()["data"]["points"]] == [
        None,
        2.871234567890123,
    ]
    assert [point["value"] for point in series.json()["data"]["points"]] == [2.871234567890123]
    assert "2.871234567890123" in curve.text
    assert "2.871234567890123" in series.text


@pytest.mark.parametrize(
    "path",
    [
        "/v1/curves/ecb-aaa-spot/observations",
        "/v1/curves/ecb-aaa-spot/maturities/10Y/observations",
        "/v1/curves/ecb-aaa-spot/maturities/10Y/observations/2026-03-12/versions",
        "/v1/curves/ecb-aaa-spot/changes",
        "/v1/curves/ecb-aaa-spot/quality",
    ],
)
def test_real_curve_answers_carry_the_ecb_attribution(client: TestClient, path: str) -> None:
    params = {"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()}
    response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.json()["meta"]["source_attribution"] == "Source: ECB statistics"


@pytest.mark.parametrize(
    "path",
    [
        "/v1/curves/ecb-aaa-spot-sim/observations",
        "/v1/curves/ecb-aaa-spot-sim/maturities/10Y/observations",
        "/v1/curves/ecb-aaa-spot-sim/maturities/10Y/observations/2026-03-12/versions",
        "/v1/curves/ecb-aaa-spot-sim/changes",
        "/v1/curves/ecb-aaa-spot-sim/quality",
    ],
)
def test_simulated_curve_answers_carry_the_simulated_note(client: TestClient, path: str) -> None:
    params = {"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()}
    response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.json()["meta"]["source_attribution"] == (
        "Simulated scenario based on ECB statistics"
    )


def test_an_unknown_curve_is_not_found(client: TestClient, services: FakeServices) -> None:
    response = client.get("/v1/curves/unknown/observations")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"
    assert response.json()["detail"] == "no curve named unknown"
    assert services.curves.calls == []


def test_a_flagged_value_carries_its_status_and_flags(
    client: TestClient, services: FakeServices
) -> None:
    services.quality.known = {
        7: ValueQuality(
            status=QualityStatus.WARN,
            flags=(
                QualityFlag(
                    rule="range",
                    severity=Severity.WARN,
                    explanation="Yield is outside the plausible range",
                    evidence="26.4 % is above 15 %",
                ),
                QualityFlag(
                    rule="jump",
                    severity=Severity.WARN,
                    explanation="Yield jumped more than expected",
                    evidence="26.4 % vs 2.5 % on the previous day",
                ),
            ),
        )
    }

    response = client.get(CURVE_PATH)
    point = response.json()["data"]["points"][1]

    assert point["quality"]["status"] == "warn"
    assert {flag["rule"] for flag in point["quality"]["flags"]} == {"range", "jump"}
    assert all(flag["explanation"] and flag["evidence"] for flag in point["quality"]["flags"])


def test_a_value_without_result_is_unchecked(client: TestClient, services: FakeServices) -> None:
    services.quality.known = {}

    response = client.get(CURVE_PATH)

    assert response.json()["data"]["points"][1]["quality"] == UNCHECKED_QUALITY


def test_processing_unavailable_marks_values_unchecked_and_not_immutable(
    client: TestClient, services: FakeServices
) -> None:
    services.quality.unavailable = True

    response = client.get(CURVE_PATH, params={"as_of": AS_OF.isoformat()})

    assert response.json()["data"]["points"][1]["quality"] == UNCHECKED_QUALITY
    assert response.headers["cache-control"] == "no-cache"


def test_a_settled_answer_with_every_value_checked_is_immutable(
    client: TestClient, services: FakeServices
) -> None:
    services.quality.known = {7: ValueQuality(status=QualityStatus.PASSED, flags=())}

    response = client.get(CURVE_PATH, params={"as_of": AS_OF.isoformat()})

    assert response.json()["data"]["points"][1]["quality"] == PASSED_QUALITY
    assert response.headers["cache-control"] == IMMUTABLE


def test_quality_endpoint_returns_days_from_processing(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(
        QUALITY_PATH,
        params={"from": "2026-03-12", "to": "2026-03-14", "as_of": AS_OF.isoformat()},
    )

    assert response.status_code == 200
    assert services.quality.days_calls == [
        ("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), AS_OF)
    ]
    payload = response.json()
    assert payload["meta"]["as_of"] == "2026-03-13T08:00:00Z"
    day = payload["data"]["days"][0]
    assert day["valid_date"] == "2026-03-12"
    assert day["status"] == "warn"
    assert day["findings"][0]["rule"] == "range"


def test_quality_endpoint_is_503_when_processing_is_unavailable(
    client: TestClient, services: FakeServices
) -> None:
    services.quality.days_error = ProcessingUnavailableError()

    response = client.get(QUALITY_PATH, params={"from": "2026-03-12", "to": "2026-03-14"})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == ("The quality service is not reachable; try again later.")


def test_quality_answers_are_never_immutable(client: TestClient) -> None:
    response = client.get(
        QUALITY_PATH,
        params={"from": "2026-03-12", "to": "2026-03-14", "as_of": AS_OF.isoformat()},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert "etag" in response.headers


def test_quality_answers_304_when_etag_matches(client: TestClient) -> None:
    params = {"from": "2026-03-12", "to": "2026-03-14", "as_of": AS_OF.isoformat()}
    first = client.get(QUALITY_PATH, params=params)

    response = client.get(
        QUALITY_PATH,
        params=params,
        headers={"If-None-Match": first.headers["etag"]},
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "no-cache"


def test_an_unknown_curve_is_404(client: TestClient, services: FakeServices) -> None:
    response = client.get(
        "/v1/curves/unknown/quality",
        params={"from": "2026-03-12", "to": "2026-03-14"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "no curve named unknown"
    assert services.quality.days_calls == []


UNEXPECTED_TRACE_ID = 0x0AF7651916CD43DD8448EB211C80319C
UNEXPECTED_SPAN_ID = 0xB7AD6B7169203331


def _app_that_raises(services: FakeServices) -> FastAPI:
    app = create_app(services.open, cors_origins=[])

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("ORA-00942: table SECRET_TABLE does not exist")

    return app


def test_an_unexpected_error_is_a_generic_problem(
    services: FakeServices, caplog: pytest.LogCaptureFixture
) -> None:
    with TestClient(_app_that_raises(services), raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal server error",
        "status": 500,
        "detail": "An unexpected error occurred.",
    }
    assert "ORA-00942" not in response.text
    assert "RuntimeError" not in response.text
    # A 500 is never cached: the generic error carries no validators or cache directives.
    assert "etag" not in response.headers
    assert "cache-control" not in response.headers
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError
    assert getattr(record, "event") == "unexpected_error"  # noqa: B009


def test_an_unexpected_error_carries_the_trace_id(
    services: FakeServices, caplog: pytest.LogCaptureFixture
) -> None:
    app = _app_that_raises(services)
    span_context = SpanContext(
        trace_id=UNEXPECTED_TRACE_ID,
        span_id=UNEXPECTED_SPAN_ID,
        is_remote=False,
    )

    async def traced(scope: Scope, receive: Receive, send: Send) -> None:
        with trace.use_span(NonRecordingSpan(span_context)):
            await app(scope, receive, send)

    with TestClient(traced, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    expected = "0af7651916cd43dd8448eb211c80319c"
    assert response.status_code == 500
    assert response.json()["trace_id"] == expected
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert getattr(record, "trace_id") == expected  # noqa: B009


def test_measures_in_the_public_envelope(client: TestClient) -> None:
    response = client.get(MEASURES_PATH, params={"from": "2026-03-12", "to": "2026-03-12"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {
        "as_of": "2026-03-13T08:00:00Z",
        "method_version": "1",
        "source_attribution": "Source: ECB statistics",
    }
    assert payload["data"]["curve_id"] == "ecb-aaa-spot"
    point = payload["data"]["points"][0]
    assert point["valid_date"] == "2026-03-12"
    assert point["spread_2y_10y"] == 66.0
    assert point["spread_3m_10y"] is None
    assert point["inverted"] is False
    assert point["missing"] == ["3M", "5Y"]
    assert point["inputs"][0] == {
        "maturity": "2Y",
        "value": 1.98,
        "version_id": 3,
        "status": "passed",
    }
    assert point["quality"] == {"status": "passed", "flagged": []}


def test_measures_pass_range_and_as_of_to_processing(
    client: TestClient, services: FakeServices
) -> None:
    client.get(
        MEASURES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-14", "as_of": AS_OF.isoformat()},
    )

    assert services.measures.calls == [
        ("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 14), AS_OF)
    ]


def test_measures_without_as_of_pass_none_to_processing(
    client: TestClient, services: FakeServices
) -> None:
    client.get(MEASURES_PATH, params={"from": "2026-03-12", "to": "2026-03-12"})

    assert services.measures.calls == [("ecb-aaa-spot", date(2026, 3, 12), date(2026, 3, 12), None)]


def test_measures_with_a_settled_as_of_and_checked_inputs_are_immutable(
    client: TestClient,
) -> None:
    response = client.get(
        MEASURES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-12", "as_of": AS_OF.isoformat()},
    )

    assert response.headers["cache-control"] == IMMUTABLE


def test_measures_with_an_unchecked_input_are_no_cache(
    client: TestClient, services: FakeServices
) -> None:
    services.measures.result = replace(
        services.measures.result, points=(measure_point(QualityStatus.UNCHECKED),)
    )

    response = client.get(
        MEASURES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-12", "as_of": AS_OF.isoformat()},
    )

    assert response.headers["cache-control"] == "no-cache"


def test_measures_without_as_of_are_no_cache(client: TestClient) -> None:
    response = client.get(MEASURES_PATH, params={"from": "2026-03-12", "to": "2026-03-12"})

    assert response.headers["cache-control"] == "no-cache"


def test_measures_at_the_horizon_are_no_cache(client: TestClient, services: FakeServices) -> None:
    services.measures.result = replace(
        services.measures.result, as_of=datetime(2026, 3, 13, 7, 0, tzinfo=UTC)
    )

    response = client.get(
        MEASURES_PATH,
        params={"from": "2026-03-12", "to": "2026-03-12", "as_of": AS_OF.isoformat()},
    )

    assert response.headers["cache-control"] == "no-cache"


def test_measures_answer_304_for_a_matching_etag(client: TestClient) -> None:
    params = {"from": "2026-03-12", "to": "2026-03-12", "as_of": AS_OF.isoformat()}
    first = client.get(MEASURES_PATH, params=params)

    response = client.get(
        MEASURES_PATH, params=params, headers={"If-None-Match": first.headers["etag"]}
    )

    assert first.headers["etag"]
    assert response.status_code == 304


def test_measures_not_found_is_404(client: TestClient, services: FakeServices) -> None:
    services.measures.error = CurveNotFoundError("no curve named ecb-aaa-spot")

    response = client.get(MEASURES_PATH, params={"from": "2026-03-12", "to": "2026-03-12"})

    assert response.status_code == 404
    assert response.json()["detail"] == "no curve named ecb-aaa-spot"


def test_measures_invalid_range_is_422(client: TestClient, services: FakeServices) -> None:
    services.measures.error = InvalidCurveQueryError("to is before from")

    response = client.get(MEASURES_PATH, params={"from": "2026-03-14", "to": "2026-03-12"})

    assert response.status_code == 422
    assert response.json()["detail"] == "to is before from"


def test_measures_of_an_unknown_curve_are_404_without_calling_processing(
    client: TestClient, services: FakeServices
) -> None:
    response = client.get(
        "/v1/curves/unknown/measures", params={"from": "2026-03-12", "to": "2026-03-12"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "no curve named unknown"
    assert services.measures.calls == []


def test_measures_unavailable_is_503_with_the_measures_detail(
    client: TestClient, services: FakeServices
) -> None:
    services.measures.error = MeasuresUnavailableError()

    response = client.get(MEASURES_PATH, params={"from": "2026-03-12", "to": "2026-03-12"})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == MEASURES_UNAVAILABLE
