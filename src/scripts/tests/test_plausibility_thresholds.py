"""Unit tests of src/scripts/plausibility_thresholds.py: option handling and the Treasury parsing.

No network: the Treasury files are inline CSV, and urlopen and sleep are replaced.
Run with pytest (the processing service's environment has it).
"""

import importlib.util
import io
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plausibility_thresholds.py"
_spec = importlib.util.spec_from_file_location("plausibility_thresholds", SCRIPT)
assert _spec and _spec.loader
script = importlib.util.module_from_spec(_spec)
sys.modules["plausibility_thresholds"] = script
_spec.loader.exec_module(script)

# 1990 layout: nine columns, no 20 Yr (the 1990 header of the Treasury file).
CSV_1990 = (
    "Date,1 Mo,2 Mo,3 Mo,6 Mo,1 Yr,2 Yr,3 Yr,5 Yr,7 Yr,10 Yr,30 Yr\n"
    "01/02/1990,7.80,7.85,7.90,7.95,8.00,8.10,8.20,8.30,8.40,8.45,8.60\n"
    "01/03/1990,,7.82,7.91,,8.05,8.12,,8.31,8.41,8.46,8.61\n"
)
# Later layout with a column the script does not know (ignored) and an empty 1.5 Month cell.
CSV_2025 = (
    "Date,1 Mo,1.5 Month,2 Mo,3 Mo,4 Mo,6 Mo,1 Yr,2 Yr,3 Yr,5 Yr,7 Yr,10 Yr,20 Yr,30 Yr,Extra\n"
    "02/18/2025,4.30,,4.28,4.27,4.25,4.20,4.05,3.95,3.92,4.00,4.15,4.35,4.80,4.60,x\n"
)


def test_parse_ust_csv_1990_layout_gives_points_and_empty_tenors() -> None:
    series = script.parse_ust_csv(io.StringIO(CSV_1990))
    assert series["3M"] == [("1990-01-02", 7.90), ("1990-01-03", 7.91)]
    assert series["1M"] == [
        ("1990-01-02", 7.80)
    ]  # the empty cell on 1990-01-03 is no value
    assert series["1.5M"] == []  # column absent: not yet published
    assert series["20Y"] == []  # column absent in 1990
    assert series["30Y"] == [("1990-01-02", 8.60), ("1990-01-03", 8.61)]


def test_parse_ust_csv_later_layout_ignores_unknown_and_reads_new_tenors() -> None:
    series = script.parse_ust_csv(io.StringIO(CSV_2025))
    assert set(series) == set(script.UST_TENORS.values())
    assert series["1.5M"] == []  # empty cell
    assert series["20Y"] == [("2025-02-18", 4.80)]
    assert series["1M"] == [("2025-02-18", 4.30)]


def test_parse_ust_csv_handles_bom_when_read_as_utf8_sig(tmp_path: Path) -> None:
    raw = ("﻿" + CSV_1990).encode("utf-8")
    text = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8-sig")
    assert script.parse_ust_csv(text)["3M"][0] == ("1990-01-02", 7.90)


def test_ust_year_urls_cover_1990_to_last_year() -> None:
    urls = script.ust_year_urls(2026)
    assert len(urls) == 37
    assert "/1990/all?" in urls[0] and "field_tdr_date_value=1990" in urls[0]
    assert "field_tdr_date_value=2026" in urls[-1]


def test_fetch_ust_history_pauses_between_requests_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []
    slept: list[float] = []
    bodies = {1990: CSV_1990, 1991: CSV_2025}

    def fake_urlopen(request, timeout):
        url = request.full_url
        requested.append(url)
        year = int(url.split("/daily-treasury-rates.csv/")[1][:4])
        return io.BytesIO(bodies[year].encode("utf-8"))

    monkeypatch.setattr(script.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(script.time, "sleep", slept.append)

    series = script.fetch_ust_history(1991)
    assert len(requested) == 2
    assert slept == [script.UST_PAUSE_SECONDS]
    assert script.UST_PAUSE_SECONDS >= 3
    assert series["3M"][0] == ("1990-01-02", 7.90)
    assert series["3M"][-1] == ("2025-02-18", 4.27)
    assert [day for day, _ in series["30Y"]] == sorted(day for day, _ in series["30Y"])


def test_parse_args_ust_takes_no_curve() -> None:
    args = script.parse_args(["--source", "ust"])
    assert args.source == "ust" and args.curve is None
    with pytest.raises(SystemExit):
        script.parse_args(["--source", "ust", "--curve", "ecb-aaa-spot"])


def test_parse_args_defaults_and_ecb_curves() -> None:
    assert script.parse_args([]).curve == "ecb-aaa-spot"
    assert (
        script.parse_args(["--source", "ecb", "--curve", "ecb-all-spot"]).curve
        == "ecb-all-spot"
    )
    with pytest.raises(SystemExit):
        script.parse_args(["--source", "ecb", "--curve", "ust-par"])


def test_parse_args_rejects_unknown_source() -> None:
    with pytest.raises(SystemExit):
        script.parse_args(["--source", "fred"])
