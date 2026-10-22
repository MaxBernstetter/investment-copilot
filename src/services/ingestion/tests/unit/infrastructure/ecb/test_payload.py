"""The declared ECB source schema (Pandera on Polars) against recorded and broken payloads."""

import csv as csv_module
import io
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from ingestion.domain.observation import PublishedObservation
from ingestion.infrastructure.ecb.payload import (
    CURVE_IDS,
    NORMALIZATION_VERSION,
    InvalidPayloadError,
    parse_payload,
)
from tests.recorded import (
    DAILY,
    EMPTY_WINDOW,
    HISTORY_2025,
    HISTORY_2026,
    MALFORMED,
    MIXED,
    payload,
)

GRID = {"3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"}
HEADER = (
    "KEY,FREQ,REF_AREA,CURRENCY,PROVIDER_FM,INSTRUMENT_FM,PROVIDER_FM_ID,"
    "DATA_TYPE_FM,TIME_PERIOD,OBS_VALUE"
)
ROW_10Y = (
    "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y,B,U2,EUR,4F,G_N_A,SV_C_YM,SR_10Y,2026-10-01,3.5921733451"
)
ROW_10Y_ALL = ROW_10Y.replace("G_N_A", "G_N_C")
OCT_14_15 = (date(2026, 10, 14), date(2026, 10, 15))


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
        normalization_version="2",
    )


@pytest.mark.parametrize("recording", [DAILY, HISTORY_2025, HISTORY_2026])
def test_aaa_only_recordings_map_to_ecb_aaa_spot_only(recording: str) -> None:
    rows = list(csv_module.DictReader(io.StringIO(payload(recording).decode())))

    observations = parse_payload(payload(recording))

    assert {observation.curve_id for observation in observations} == {"ecb-aaa-spot"}
    assert len(observations) == len(rows)


@pytest.mark.parametrize("recording", [DAILY, HISTORY_2025, HISTORY_2026, MIXED])
def test_mapping_rules_keep_obs_value_unchanged(recording: str) -> None:
    # INSTRUMENT_FM -> curve, DATA_TYPE_FM SR_<tenor> -> tenor, TIME_PERIOD -> valid date,
    # OBS_VALUE as published.
    rows = list(csv_module.DictReader(io.StringIO(payload(recording).decode())))
    published = {
        (CURVE_IDS[row["INSTRUMENT_FM"]], row["DATA_TYPE_FM"], row["TIME_PERIOD"]): row["OBS_VALUE"]
        for row in rows
    }

    observations = parse_payload(payload(recording))

    mapped = {
        (o.curve_id, f"SR_{o.maturity}", o.valid_date.isoformat()): format(o.value, "f")
        for o in observations
    }
    assert len(observations) == len(rows)
    assert mapped == published


def test_observations_name_the_normalization_version_of_the_mapping() -> None:
    observations = parse_payload(payload(DAILY))

    assert NORMALIZATION_VERSION == "2"
    assert {observation.normalization_version for observation in observations} == {"2"}


def test_recorded_mixed_payload_maps_to_both_curves() -> None:
    observations = parse_payload(payload(MIXED))

    assert Counter(observation.curve_id for observation in observations) == {
        "ecb-aaa-spot": 22,
        "ecb-all-spot": 22,
    }
    for curve_id in CURVE_IDS.values():
        own = [observation for observation in observations if observation.curve_id == curve_id]
        assert {observation.maturity for observation in own} == GRID
        assert {observation.valid_date for observation in own} == set(OCT_14_15)


def test_aaa_rows_of_the_mixed_payload_map_exactly_as_the_aaa_only_recording() -> None:
    mixed_aaa = {
        (o.maturity, o.valid_date, o.value)
        for o in parse_payload(payload(MIXED))
        if o.curve_id == "ecb-aaa-spot"
    }
    daily_same_days = {
        (o.maturity, o.valid_date, o.value)
        for o in parse_payload(payload(DAILY))
        if o.valid_date in OCT_14_15
    }

    assert mixed_aaa == daily_same_days


def test_the_same_tenor_and_date_of_both_instruments_are_two_observations() -> None:
    observations = parse_payload(csv(HEADER, ROW_10Y, ROW_10Y_ALL))

    assert [observation.curve_id for observation in observations] == [
        "ecb-aaa-spot",
        "ecb-all-spot",
    ]
    assert {(o.maturity, o.valid_date) for o in observations} == {("10Y", date(2026, 10, 1))}


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
        ("unknown instrument", csv(HEADER, ROW_10Y.replace("G_N_A", "G_N_B"))),
        ("key not matching the instrument", csv(HEADER, ROW_10Y.replace(",G_N_A,", ",G_N_C,"))),
        ("duplicate observation", csv(HEADER, ROW_10Y, ROW_10Y)),
        ("duplicate observation of one curve", csv(HEADER, ROW_10Y_ALL, ROW_10Y_ALL)),
        ("ragged row", csv(HEADER, ROW_10Y + ",extra")),
        ("not CSV at all", b"<html>Access denied</html>"),
    ],
)
def test_payloads_breaking_the_schema_are_rejected(description: str, content: bytes) -> None:
    with pytest.raises(InvalidPayloadError):
        parse_payload(content)
