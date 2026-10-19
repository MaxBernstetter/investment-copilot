"""The declared ECB source schema (Pandera on Polars) against recorded and broken payloads."""

import csv as csv_module
import io
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from ingestion.domain.observation import PublishedObservation
from ingestion.infrastructure.ecb.payload import (
    NORMALIZATION_VERSION,
    InvalidPayloadError,
    parse_payload,
)
from tests.recorded import DAILY, EMPTY_WINDOW, HISTORY_2025, HISTORY_2026, MALFORMED, payload

GRID = {"3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"}
HEADER = (
    "KEY,FREQ,REF_AREA,CURRENCY,PROVIDER_FM,INSTRUMENT_FM,PROVIDER_FM_ID,"
    "DATA_TYPE_FM,TIME_PERIOD,OBS_VALUE"
)
ROW_10Y = (
    "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y,B,U2,EUR,4F,G_N_A,SV_C_YM,SR_10Y,2026-10-01,3.5921733451"
)


def csv(*lines: str) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode()


def test_recorded_daily_payload_maps_to_the_11_grid_tenors_per_date() -> None:
    observations = parse_payload(payload(DAILY))

    per_date = Counter(observation.valid_date for observation in observations)
    assert len(per_date) == 11
    assert set(per_date.values()) == {11}
    assert {observation.maturity for observation in observations} == GRID
    assert {observation.curve_id for observation in observations} == {"ecb-aaa-spot"}


def test_values_keep_the_published_digits() -> None:
    observations = parse_payload(payload(DAILY))

    assert observations[0] == PublishedObservation(
        curve_id="ecb-aaa-spot",
        maturity="10Y",
        valid_date=date(2026, 10, 1),
        value=Decimal("3.5921733451"),
        normalization_version="1",
    )


@pytest.mark.parametrize("recording", [DAILY, HISTORY_2025, HISTORY_2026])
def test_mapping_rules_keep_obs_value_unchanged(recording: str) -> None:
    # DATA_TYPE_FM SR_<tenor> -> tenor, TIME_PERIOD -> valid date, OBS_VALUE as published.
    rows = list(csv_module.DictReader(io.StringIO(payload(recording).decode())))
    published = {(row["DATA_TYPE_FM"], row["TIME_PERIOD"]): row["OBS_VALUE"] for row in rows}

    observations = parse_payload(payload(recording))

    mapped = {
        (f"SR_{o.maturity}", o.valid_date.isoformat()): format(o.value, "f") for o in observations
    }
    assert len(observations) == len(rows)
    assert mapped == published


def test_observations_name_the_normalization_version_of_the_mapping() -> None:
    observations = parse_payload(payload(DAILY))

    assert NORMALIZATION_VERSION == "1"
    assert {observation.normalization_version for observation in observations} == {"1"}


def test_an_empty_delivery_has_no_observations() -> None:
    assert parse_payload(payload(EMPTY_WINDOW)) == []


def test_extra_columns_are_tolerated() -> None:
    observations = parse_payload(csv(HEADER + ",OBS_STATUS", ROW_10Y + ",A"))

    assert [observation.maturity for observation in observations] == ["10Y"]


def test_crafted_malformed_payload_reports_the_date_and_the_value() -> None:
    with pytest.raises(InvalidPayloadError) as raised:
        parse_payload(payload(MALFORMED))

    message = str(raised.value)
    assert "06.10.2026" in message
    assert "NaN" in message


@pytest.mark.parametrize(
    ("description", "content"),
    [
        ("missing column", csv(HEADER.removesuffix(",OBS_VALUE"), ROW_10Y.rsplit(",", 1)[0])),
        ("empty value", csv(HEADER, ROW_10Y.rsplit(",", 1)[0] + ",")),
        ("non-numeric value", csv(HEADER, ROW_10Y.replace("3.5921733451", "3,59"))),
        ("non-ISO date", csv(HEADER, ROW_10Y.replace("2026-10-01", "2026/10/01"))),
        ("impossible date", csv(HEADER, ROW_10Y.replace("2026-10-01", "2026-02-30"))),
        ("tenor off the grid", csv(HEADER, ROW_10Y.replace("SR_10Y", "SR_4Y"))),
        ("key not matching the tenor", csv(HEADER, ROW_10Y.replace("SR_10Y,B", "SR_5Y,B"))),
        ("other curve", csv(HEADER, ROW_10Y.replace("G_N_A", "G_N_C"))),
        ("duplicate observation", csv(HEADER, ROW_10Y, ROW_10Y)),
        ("ragged row", csv(HEADER, ROW_10Y + ",extra")),
        ("not CSV at all", b"<html>Access denied</html>"),
    ],
)
def test_payloads_breaking_the_schema_are_rejected(description: str, content: bytes) -> None:
    with pytest.raises(InvalidPayloadError):
        parse_payload(content)
