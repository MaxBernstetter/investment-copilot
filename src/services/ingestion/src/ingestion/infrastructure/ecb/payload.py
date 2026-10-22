"""Declared source schema of the ECB spot-curve CSV and its mapping to observations.

The payload is ``format=csvdata&detail=dataonly`` of the SDMX REST API: one row per
series and date. Every column is read as text, so ``OBS_VALUE`` keeps the exact digits
the ECB published (ESCB reuse terms: published statistics are not modified).
"""

import io
from datetime import date
from decimal import Decimal
from typing import ClassVar

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaError, SchemaErrors

from ingestion.domain.observation import PublishedObservation

SCHEMA_VERSION = "2"
"""Version of the declared payload schema below."""

NORMALIZATION_VERSION = "2"
"""Version of the mapping rules in ``parse_payload``: ``INSTRUMENT_FM`` to the curve
(``CURVE_IDS``), ``DATA_TYPE_FM`` ``SR_<tenor>`` to the grid tenor, ``TIME_PERIOD`` to the
valid date, ``OBS_VALUE`` unchanged. Raise it whenever the mapping changes, so every stored
value names the rules that produced it. Version 2 added the instrument to curve mapping."""

CURVE_IDS: dict[str, str] = {"G_N_A": "ecb-aaa-spot", "G_N_C": "ecb-all-spot"}
"""``INSTRUMENT_FM`` to curve: euro area government bonds of AAA-rated issuers (``G_N_A``)
and of all issuers (``G_N_C``), both Svensson model, spot rates."""
INSTRUMENTS = tuple(CURVE_IDS)

GRID_TENORS = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
DATA_TYPES = tuple(f"SR_{tenor}" for tenor in GRID_TENORS)
"""``DATA_TYPE_FM`` of the spot rates on the grid: ``SR_<tenor>``."""


def series_key(instrument: str, data_type: str) -> str:
    """SDMX key in dataset ``YC``; either part may join several codes with ``+``."""
    return f"B.U2.EUR.4F.{instrument}.SV_C_YM.{data_type}"


ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"
DECIMAL_NUMBER = r"^-?\d+(\.\d+)?$"


class InvalidPayloadError(Exception):
    """The delivery does not match the declared source schema; nothing of it is used."""


class EcbSpotCurvePayload(pa.DataFrameModel):
    """Declared schema (version ``SCHEMA_VERSION``). Extra columns are tolerated."""

    KEY: str = pa.Field(
        isin=[
            f"YC.{series_key(instrument, data_type)}"
            for instrument in INSTRUMENTS
            for data_type in DATA_TYPES
        ]
    )
    FREQ: str = pa.Field(eq="B")
    REF_AREA: str = pa.Field(eq="U2")
    CURRENCY: str = pa.Field(eq="EUR")
    PROVIDER_FM: str = pa.Field(eq="4F")
    INSTRUMENT_FM: str = pa.Field(isin=list(INSTRUMENTS))
    PROVIDER_FM_ID: str = pa.Field(eq="SV_C_YM")
    DATA_TYPE_FM: str = pa.Field(isin=list(DATA_TYPES))
    TIME_PERIOD: str = pa.Field(str_matches=ISO_DATE)
    OBS_VALUE: str = pa.Field(str_matches=DECIMAL_NUMBER)

    class Config:
        unique: ClassVar[list[str]] = ["INSTRUMENT_FM", "DATA_TYPE_FM", "TIME_PERIOD"]

    @pa.check("TIME_PERIOD", name="is_calendar_date")
    @classmethod
    def _is_calendar_date(cls, data: pa.PolarsData) -> pl.LazyFrame:
        column = pl.col(data.key)
        return data.lazyframe.select(column.str.to_date("%Y-%m-%d", strict=False).is_not_null())

    @pa.dataframe_check(name="key_matches_series")
    @classmethod
    def _key_matches_series(cls, data: pa.PolarsData) -> pl.LazyFrame:
        expected = pl.concat_str(
            [
                pl.lit("YC.B.U2.EUR.4F."),
                pl.col("INSTRUMENT_FM"),
                pl.lit(".SV_C_YM."),
                pl.col("DATA_TYPE_FM"),
            ]
        )
        return data.lazyframe.select(pl.col("KEY") == expected)


def parse_payload(content: bytes) -> list[PublishedObservation]:
    """Validate a CSV delivery and map it to observations (empty content: none).

    Raises ``InvalidPayloadError`` if the CSV is unreadable or breaks the schema.
    """
    if not content.strip():
        return []
    try:
        frame = pl.read_csv(io.BytesIO(content), infer_schema=False)
        validated = EcbSpotCurvePayload.validate(frame, lazy=True)
    except (pl.exceptions.PolarsError, SchemaError, SchemaErrors) as error:
        raise InvalidPayloadError(f"ECB payload breaks schema {SCHEMA_VERSION}: {error}") from error
    return [
        PublishedObservation(
            curve_id=CURVE_IDS[instrument],
            maturity=data_type.removeprefix("SR_"),
            valid_date=date.fromisoformat(time_period),
            value=Decimal(obs_value),
            normalization_version=NORMALIZATION_VERSION,
        )
        for instrument, data_type, time_period, obs_value in validated.select(
            "INSTRUMENT_FM", "DATA_TYPE_FM", "TIME_PERIOD", "OBS_VALUE"
        ).iter_rows()
    ]
