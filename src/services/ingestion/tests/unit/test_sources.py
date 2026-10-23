import pytest

from ingestion.config import SourcesSettings
from ingestion.infrastructure.ecb import EcbSpotCurveSource
from ingestion.infrastructure.ust import UstParCurveSource
from ingestion.sources import SOURCES, wiring


def test_ecb_is_wired() -> None:
    assert wiring("ecb").source_id == "ecb"
    assert wiring("ecb").make_curve_source is EcbSpotCurveSource


def test_ust_is_wired() -> None:
    assert wiring("ust").source_id == "ust"
    assert wiring("ust").make_curve_source is UstParCurveSource


def test_every_wired_source_has_a_settings_slot() -> None:
    settings = SourcesSettings()

    for source_id in SOURCES:
        settings.for_source(source_id)


def test_unknown_source_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="unknown source 'nope'"):
        wiring("nope")
