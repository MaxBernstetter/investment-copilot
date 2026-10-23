"""Declared source schema of the US Treasury daily par yield curve CSV and its mapping.

One CSV per calendar year: a ``Date`` column (``MM/DD/YYYY``, newest first) and one column
per tenor. The set of tenor columns drifts over the years: a tenor is absent before it was
introduced (1990 has no ``20 Yr``, 2004 no ``30 Yr``), and a column may be present but empty
for the days before its first publication (``1.5 Month``). An empty cell is no observation.

Every column is read as text, so the value keeps the exact digits the Treasury published
(percent per annum, par yields, bond-equivalent basis, unchanged).
"""

import io
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaError, SchemaErrors

from ingestion.domain.observation import PublishedObservation

SCHEMA_VERSION = "1"
"""Version of the declared payload schema below."""

NORMALIZATION_VERSION = "1"
"""Version of the mapping rules in ``parse_payload``: each tenor column to its grid tenor
(``COLUMN_TENORS``), ``Date`` to the valid date, the value unchanged. Raise it whenever the
mapping changes, so every stored value names the rules that produced it."""

CURVE_ID = "ust-par"

COLUMN_TENORS: dict[str, str] = {
    "1 Mo": "1M",
    "1.5 Month": "1.5M",
    "2 Mo": "2M",
    "3 Mo": "3M",
    "4 Mo": "4M",
    "6 Mo": "6M",
    "1 Yr": "1Y",
    "2 Yr": "2Y",
    "3 Yr": "3Y",
    "5 Yr": "5Y",
    "7 Yr": "7Y",
    "10 Yr": "10Y",
    "20 Yr": "20Y",
    "30 Yr": "30Y",
}
"""Tenor column header to grid 2 maturity. The Treasury publishes no 15-year par yield, so
grid 2's 15Y has no column; 1.5M is the 1.5-month bill, a decimal number of months."""

ISO_TEXT_DATE = r"^\d{2}/\d{2}/\d{4}$"
DECIMAL_NUMBER = r"^-?\d+(\.\d+)?$"
DATE_FORMAT = "%m/%d/%Y"


class InvalidPayloadError(Exception):
    """The delivery does not match the declared source schema; nothing of it is used."""


def _tenor_field(alias: str, *, required: bool) -> Any:
    """A tenor column: a nullable decimal (an empty cell is no observation)."""
    return pa.Field(alias=alias, nullable=True, required=required, str_matches=DECIMAL_NUMBER)


class UstParCurvePayload(pa.DataFrameModel):
    """Declared schema (version ``SCHEMA_VERSION``). Extra columns are tolerated and reported."""

    date_: str = pa.Field(alias="Date", str_matches=ISO_TEXT_DATE)
    m_1: str = _tenor_field("1 Mo", required=False)
    m_1_5: str = _tenor_field("1.5 Month", required=False)
    m_2: str = _tenor_field("2 Mo", required=False)
    m_3: str = _tenor_field("3 Mo", required=True)
    m_4: str = _tenor_field("4 Mo", required=False)
    m_6: str = _tenor_field("6 Mo", required=True)
    y_1: str = _tenor_field("1 Yr", required=True)
    y_2: str = _tenor_field("2 Yr", required=True)
    y_3: str = _tenor_field("3 Yr", required=True)
    y_5: str = _tenor_field("5 Yr", required=True)
    y_7: str = _tenor_field("7 Yr", required=True)
    y_10: str = _tenor_field("10 Yr", required=True)
    y_20: str = _tenor_field("20 Yr", required=False)
    y_30: str = _tenor_field("30 Yr", required=False)

    class Config:
        strict = False
        unique: ClassVar[list[str]] = ["Date"]

    @pa.check("Date", name="is_calendar_date")
    @classmethod
    def _is_calendar_date(cls, data: pa.PolarsData) -> pl.LazyFrame:
        column = pl.col(data.key)
        return data.lazyframe.select(column.str.to_date("%m/%d/%Y", strict=False).is_not_null())


def parse_payload(content: bytes) -> tuple[list[PublishedObservation], tuple[str, ...]]:
    """Validate a CSV delivery; returns its observations and the headers of unknown columns.

    Empty content is no observation. Raises ``InvalidPayloadError`` if the CSV is unreadable,
    misses a required column or breaks the schema.
    """
    if not content.strip():
        return [], ()
    try:
        frame = pl.read_csv(io.BytesIO(content), infer_schema=False)
        validated = UstParCurvePayload.validate(frame, lazy=True)
    except (pl.exceptions.PolarsError, SchemaError, SchemaErrors) as error:
        raise InvalidPayloadError(f"UST payload breaks schema {SCHEMA_VERSION}: {error}") from error
    tenors = {column: tenor for column, tenor in COLUMN_TENORS.items() if column in frame.columns}
    unknown = tuple(column for column in frame.columns if column not in KNOWN_COLUMNS)
    return _observations(validated, tenors), unknown


KNOWN_COLUMNS = frozenset(("Date", *COLUMN_TENORS))


def _observations(frame: pl.DataFrame, tenors: Mapping[str, str]) -> list[PublishedObservation]:
    observations: list[PublishedObservation] = []
    for row in frame.select(["Date", *tenors]).iter_rows(named=True):
        valid_date = datetime.strptime(row["Date"], DATE_FORMAT).date()
        for column, tenor in tenors.items():
            text = row[column]
            if text is not None:
                observations.append(
                    PublishedObservation(
                        curve_id=CURVE_ID,
                        maturity=tenor,
                        valid_date=valid_date,
                        value=Decimal(text),
                        normalization_version=NORMALIZATION_VERSION,
                    )
                )
    return observations
