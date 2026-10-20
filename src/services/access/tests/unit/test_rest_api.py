import re
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from access.domain.changes import CurveChanges, ValueChange
from access.domain.curve import (
    CurveAsOf,
    CurveNotFoundError,
    CurvePoint,
    InvalidCurveQueryError,
    PersistenceUnavailableError,
)
from access.domain.series import Series, SeriesPoint
from access.domain.versions import ChangeReason, ValueVersion, ValueVersions
from access.facade.rest.app import Services, create_app

FRONTEND_ORIGIN = "http://localhost:5174"
CURVE_PATH = "/v1/curves/ecb-aaa-spot/observations"
SERIES_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations"
VERSIONS_PATH = "/v1/curves/ecb-aaa-spot/maturities/10Y/observations/2026-03-12/versions"
CHANGES_PATH = "/v1/curves/ecb-aaa-spot/changes"
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


class FakeServices:
    def __init__(self) -> None:
        self.ready = True
        self.curves = FakeCurveReader()

    async def is_ready(self) -> bool:
        return self.ready

    @asynccontextmanager
    async def open(self) -> AsyncIterator[Services]:
        yield Services(self.is_ready, self.curves)


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
                },
                {
                    "maturity": "10Y",
                    "months": 120,
                    "value": 2.61,
                    "version_id": 7,
                    "origin": "published",
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
                },
                {
                    "maturity": "10Y",
                    "months": 120,
                    "value": 2.61,
                    "version_id": 7,
                    "origin": "published",
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
    ],
)
def test_simulated_curve_answers_carry_the_simulated_note(client: TestClient, path: str) -> None:
    params = {"from": "2026-03-12", "to": "2026-03-14", "since": SINCE.isoformat()}
    response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.json()["meta"]["source_attribution"] == (
        "Simulated scenario based on ECB statistics"
    )


def test_a_curve_without_attribution_is_not_found(client: TestClient) -> None:
    response = client.get("/v1/curves/unknown/observations")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Not found"
    assert response.json()["detail"] == "no curve named unknown"
