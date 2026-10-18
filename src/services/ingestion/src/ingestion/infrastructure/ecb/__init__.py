"""ECB Data Portal: the euro area AAA spot curve (phase 1 source, ADR 0016)."""

from ingestion.infrastructure.ecb.payload import CURVE_ID, InvalidPayloadError
from ingestion.infrastructure.ecb.source import SOURCE_ID, EcbSpotCurveSource, is_no_data

__all__ = ["CURVE_ID", "SOURCE_ID", "EcbSpotCurveSource", "InvalidPayloadError", "is_no_data"]
