"""Client of the processing service: value quality and per-day quality reads."""

import json
import logging
from datetime import date, datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx
from contracts.processing import v1
from pydantic import ValidationError

from access.domain.curve import (
    CurveNotFoundError,
    InvalidCurveQueryError,
    ProcessingUnavailableError,
)
from access.domain.quality import QualityFlag, QualityStatus, Severity, ValueQuality
from access.domain.quality_days import (
    QualityDay,
    QualityDays,
    QualityFinding,
    RuleOutcome,
)

logger = logging.getLogger(__name__)


class ProcessingClient:
    """Calls processing for value quality; transport errors become ``None`` with a log line."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def value_quality(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        maturity: str | None,
        as_of: datetime,
    ) -> dict[int, ValueQuality] | None:
        path = v1.VALUE_QUALITY_PATH.format(curve_id=quote(curve_id, safe=""))
        params: dict[str, str] = {
            "from": valid_from.isoformat(),
            "to": valid_to.isoformat(),
            "as_of": as_of.isoformat(),
        }
        if maturity is not None:
            params["maturity"] = maturity
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            _log_unavailable(curve_id, valid_from, valid_to, maturity, error=repr(error))
            return None
        if response.status_code != httpx.codes.OK:
            _log_unavailable(
                curve_id,
                valid_from,
                valid_to,
                maturity,
                status_code=response.status_code,
            )
            return None
        return _to_domain(v1.ValueQualityResponse.model_validate_json(response.content))

    async def quality_days(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime | None,
    ) -> QualityDays:
        path = v1.QUALITY_DAYS_PATH.format(curve_id=quote(curve_id, safe=""))
        params: dict[str, str] = {
            "from": valid_from.isoformat(),
            "to": valid_to.isoformat(),
        }
        if as_of is not None:
            params["as_of"] = as_of.isoformat()
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise ProcessingUnavailableError from error
        if response.status_code == httpx.codes.OK:
            return _days_to_domain(_parse_quality_days(response))
        if response.status_code == httpx.codes.NOT_FOUND:
            raise CurveNotFoundError(_problem_detail(response))
        if response.status_code == 422:
            raise InvalidCurveQueryError(_problem_detail(response))
        raise ProcessingUnavailableError(f"processing answered {response.status_code}")


def _parse_quality_days(response: httpx.Response) -> v1.QualityDaysResponse:
    try:
        return v1.QualityDaysResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise ProcessingUnavailableError("processing sent an unexpected quality body") from error


def _log_unavailable(
    curve_id: str,
    valid_from: date,
    valid_to: date,
    maturity: str | None,
    **fields: object,
) -> None:
    logger.warning(
        json.dumps(
            {
                "event": "processing_value_quality_unavailable",
                "curve_id": curve_id,
                "valid_from": valid_from.isoformat(),
                "valid_to": valid_to.isoformat(),
                "maturity": maturity,
                **fields,
            }
        )
    )


def _to_domain(response: v1.ValueQualityResponse) -> dict[int, ValueQuality]:
    return {
        item.version_id: ValueQuality(
            status=QualityStatus(item.status),
            flags=tuple(_to_flag(flag) for flag in item.flags),
        )
        for item in response.data.values
    }


def _to_flag(finding: v1.Finding) -> QualityFlag:
    return QualityFlag(
        rule=finding.rule.value,
        severity=Severity(finding.severity),
        explanation=finding.explanation,
        evidence=finding.evidence,
    )


def _days_to_domain(response: v1.QualityDaysResponse) -> QualityDays:
    return QualityDays(
        curve_id=response.data.curve_id,
        valid_from=response.data.valid_from,
        valid_to=response.data.valid_to,
        as_of=response.meta.as_of,
        days=tuple(_day_to_domain(day) for day in response.data.days),
    )


def _day_to_domain(day: v1.QualityDay) -> QualityDay:
    return QualityDay(
        valid_date=day.valid_date,
        status=QualityStatus(day.status),
        run_id=day.run_id,
        checked_as_of=day.checked_as_of,
        rules=tuple(
            RuleOutcome(
                rule=rule.rule.value,
                outcome=QualityStatus(rule.outcome),
                finding_count=rule.finding_count,
            )
            for rule in day.rules
        ),
        findings=tuple(_day_finding(finding) for finding in day.findings),
    )


def _day_finding(finding: v1.Finding) -> QualityFinding:
    return QualityFinding(
        rule=finding.rule.value,
        severity=Severity(finding.severity),
        maturity=finding.maturity,
        version_id=finding.version_id,
        value=finding.value,
        explanation=finding.explanation,
        evidence=finding.evidence,
    )


def _problem_detail(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        return response.text
    detail: object = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    return response.text
