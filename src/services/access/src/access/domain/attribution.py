"""Attribution of the source values, required by the ESCB reuse terms, per curve."""

from access.domain.curve import CurveNotFoundError

SOURCE_ATTRIBUTION: dict[str, str] = {
    "ecb-aaa-spot": "Source: ECB statistics",
    "ecb-aaa-spot-sim": "Simulated scenario based on ECB statistics",
}


def source_attribution(curve_id: str) -> str:
    """The attribution of a curve; a curve without an attribution entry is not found."""
    try:
        return SOURCE_ATTRIBUTION[curve_id]
    except KeyError:
        raise CurveNotFoundError(f"no curve named {curve_id}") from None
