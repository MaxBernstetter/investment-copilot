"""ECB Data Portal: the euro area AAA and all-issuer spot curves (ADR 0016, #264)."""

from ingestion.infrastructure.ecb.payload import CURVE_IDS, InvalidPayloadError
from ingestion.infrastructure.ecb.source import (
    SOURCE_ID,
    EcbSpotCurveSource,
    is_no_data,
    parse_delivery,
)

__all__ = [
    "CURVE_IDS",
    "SOURCE_ID",
    "EcbSpotCurveSource",
    "InvalidPayloadError",
    "is_no_data",
    "parse_delivery",
]
