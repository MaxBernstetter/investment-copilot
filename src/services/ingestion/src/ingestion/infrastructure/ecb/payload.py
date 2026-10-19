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

SCHEMA_VERSION = "1"
"""Version of the declared payload schema below."""

CURVE_ID = "ecb-aaa-spot"
"""Euro area AAA government bond curve, Svensson model, spot rates."""

SERIES_PREFIX = "B.U2.EUR.4F.G_N_A.SV_C_YM."
GRID_TENORS = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
DATA_TYPES = tuple(f"SR_{tenor}" for tenor in GRID_TENORS)
"""``DATA_TYPE_FM`` of the spot rates on the grid: ``SR_<tenor>``."""

ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"
DECIMAL_NUMBER = r"^-?\d+(\.\d+)?$"


class InvalidPayloadError(Exception):
    """The delivery does not match the declared source schema; nothing of it is used."""


class EcbSpotCurvePayload(pa.DataFrameModel):
    """Declared schema (version ``SCHEMA_VERSION``). Extra columns are tolerated."""

    KEY: str = pa.Field(isin=[f"YC.{SERIES_PREFIX}{data_type}" for data_type in DATA_TYPES])
    FREQ: str = pa.Field(eq="B")
    REF_AREA: str = pa.Field(eq="U2")
    CURRENCY: str = pa.Field(eq="EUR")
    PROVIDER_FM: str = pa.Field(eq="4F")
    INSTRUMENT_FM: str = pa.Field(eq="G_N_A")
    PROVIDER_FM_ID: str = pa.Field(eq="SV_C_YM")
    DATA_TYPE_FM: str = pa.Field(isin=list(DATA_TYPES))
    TIME_PERIOD: str = pa.Field(str_matches=ISO_DATE)
    OBS_VALUE: str = pa.Field(str_matches=DECIMAL_NUMBER)

    class Config:
        unique: ClassVar[list[str]] = ["DATA_TYPE_FM", "TIME_PERIOD"]

    @pa.check("TIME_PERIOD", name="is_calendar_date")
    @classmethod
    def _is_calendar_date(cls, data: pa.PolarsData) -> pl.LazyFrame:
        column = pl.col(data.key)
        return data.lazyframe.select(column.str.to_date("%Y-%m-%d", strict=False).is_not_null())

    @pa.dataframe_check(name="key_matches_data_type")
    @classmethod
    def _key_matches_data_type(cls, data: pa.PolarsData) -> pl.LazyFrame:
        expected = pl.lit(f"YC.{SERIES_PREFIX}") + pl.col("DATA_TYPE_FM")
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
            curve_id=CURVE_ID,
            maturity=data_type.removeprefix("SR_"),
            valid_date=date.fromisoformat(time_period),
            value=Decimal(obs_value),
        )
        for data_type, time_period, obs_value in validated.select(
            "DATA_TYPE_FM", "TIME_PERIOD", "OBS_VALUE"
        ).iter_rows()
    ]
