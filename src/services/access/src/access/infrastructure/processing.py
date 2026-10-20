"""Client of the processing service: value quality reads."""

import json
import logging
from datetime import date, datetime
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx
from contracts.processing import v1

from access.domain.quality import QualityFlag, QualityStatus, Severity, ValueQuality

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
