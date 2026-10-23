"""The source registry: which adapter serves which source id.

The composition root of the load job looks a source up here. Adding a source means an
adapter, an entry in ``SOURCES``, a settings slot in ``ingestion.config.SourcesSettings``
and a console script line; nothing else in the job changes.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

from ingestion.application.load_published_curve import CurveSource
from ingestion.domain.delivery import RawDelivery
from ingestion.domain.observation import PublishedObservation
from ingestion.infrastructure.ecb import EcbSpotCurveSource
from ingestion.infrastructure.ecb import is_no_data as ecb_is_no_data
from ingestion.infrastructure.ecb import parse_delivery as ecb_parse_delivery
from ingestion.infrastructure.http import SourceClient


@dataclass(frozen=True, slots=True)
class SourceWiring:
    """What the load job needs to know about one source."""

    source_id: str
    description: str
    """The argparse description of the job's command line."""
    make_curve_source: Callable[[SourceClient], CurveSource]
    parse_delivery: Callable[[RawDelivery], list[PublishedObservation]]
    is_no_data: Callable[[httpx.Response], bool]


SOURCES: Mapping[str, SourceWiring] = {
    "ecb": SourceWiring(
        source_id="ecb",
        description=(
            "Load the ECB euro area spot curves (AAA and all issuers) into the bitemporal core."
        ),
        make_curve_source=EcbSpotCurveSource,
        parse_delivery=ecb_parse_delivery,
        is_no_data=ecb_is_no_data,
    ),
}


def wiring(source_id: str) -> SourceWiring:
    """The wiring of ``source_id``; an unknown id is a ``ValueError``."""
    try:
        return SOURCES[source_id]
    except KeyError:
        raise ValueError(f"unknown source {source_id!r}") from None
