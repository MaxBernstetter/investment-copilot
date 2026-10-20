"""Attribution of the source values, required by the ESCB reuse terms, per curve."""

SOURCE_ATTRIBUTION: dict[str, str] = {
    "ecb-aaa-spot": "Source: ECB statistics",
    "ecb-aaa-spot-sim": "Simulated scenario based on ECB statistics",
}


def source_attribution(curve_id: str) -> str:
    """The attribution of a curve; an unknown curve fails with ``KeyError``."""
    return SOURCE_ATTRIBUTION[curve_id]
