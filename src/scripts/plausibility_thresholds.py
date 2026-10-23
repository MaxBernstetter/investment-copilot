"""Derive the plausibility thresholds of a curve from its full published history.

Reads every maturity's time series through the public access API of a running
stack (load the history first, e.g. ``task dev:seed START=2004-09-06``) and prints
the statistics the thresholds in
``docs/project/02-data-processing/01-plausibility-thresholds.md`` are based on:
the value range per maturity, the distribution of daily absolute changes, and how
often each candidate jump threshold would have been exceeded. The history is read
through the access API, or, with ``--source ecb``, in one request straight from the
ECB data API (no stack needed), or, with ``--source ust``, from the yearly Treasury
CSV files of the daily par yield curve (one request per year, 3 s apart).

Usage: python3 src/scripts/plausibility_thresholds.py [--source access|ecb|ust]
       [--access-url URL] [--curve ID]
Standard library only; no write access.
"""

import argparse
import csv
import io
import itertools
import json
import time
import urllib.request
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

MATURITIES = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
FIRST_VALID_DATE = date(2004, 9, 6)  # start of the ECB AAA spot curve series
MAX_RANGE_DAYS = 3650  # below the API's 3660-day limit per request
CANDIDATE_JUMPS_BP = (20, 25, 30, 40, 50)
ECB_URL = "https://data-api.ecb.europa.eu/service/data/YC"
ECB_INSTRUMENTS = {"ecb-aaa-spot": "G_N_A", "ecb-all-spot": "G_N_C"}
UST_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)
UST_FIRST_YEAR = 1990
UST_PAUSE_SECONDS = 3  # polite pause between the yearly requests
# CSV column of the Treasury file -> tenor label (grid 2, as in the ust-par curve)
UST_TENORS = {
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
USER_AGENT = (
    "YieldLens/plausibility-thresholds (+https://github.com/MaxBernstetter/yield-lens)"
)

Point = tuple[str, float]  # (valid date, value in percent)


def fetch_series(access_url: str, curve: str, maturity: str) -> list[Point]:
    """All published values of one maturity, oldest first, read in API-sized chunks."""
    points: list[Point] = []
    start = FIRST_VALID_DATE
    while start <= date.today():
        end = min(start + timedelta(days=MAX_RANGE_DAYS), date.today())
        url = (
            f"{access_url}/v1/curves/{curve}/maturities/{maturity}/observations"
            f"?from={start.isoformat()}&to={end.isoformat()}"
        )
        with urllib.request.urlopen(url) as response:
            data = json.load(response)["data"]
        points += [(p["valid_date"], p["value"]) for p in data["points"]]
        start = end + timedelta(days=1)
    return sorted(points)


def fetch_ecb_history(curve: str) -> dict[str, list[Point]]:
    """All published values of every maturity of ``curve``, oldest first, in one ECB request.

    One attempt with a 60 s timeout, as the ingestion job does: the script makes no retry.
    """
    data_types = "+".join(f"SR_{maturity}" for maturity in MATURITIES)
    url = (
        f"{ECB_URL}/B.U2.EUR.4F.{ECB_INSTRUMENTS[curve]}.SV_C_YM.{data_types}"
        f"?startPeriod={FIRST_VALID_DATE.isoformat()}&format=csvdata&detail=dataonly"
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    series: dict[str, list[Point]] = {maturity: [] for maturity in MATURITIES}
    with urllib.request.urlopen(request, timeout=60) as response:
        for row in csv.DictReader(io.TextIOWrapper(response, encoding="utf-8")):
            if row["OBS_VALUE"]:
                maturity = row["DATA_TYPE_FM"].removeprefix("SR_")
                series[maturity].append((row["TIME_PERIOD"], float(row["OBS_VALUE"])))
    return {maturity: sorted(points) for maturity, points in series.items()}


def ust_year_urls(last_year: int) -> list[str]:
    """The yearly Treasury CSV URLs from the first published year to ``last_year``."""
    return [UST_URL.format(year=year) for year in range(UST_FIRST_YEAR, last_year + 1)]


def parse_ust_csv(lines: Iterable[str]) -> dict[str, list[Point]]:
    """Values of one yearly Treasury file per tenor label, oldest first.

    Columns not in ``UST_TENORS`` are ignored; an empty cell is no observation, and a
    tenor column missing from the file (it appeared later) yields no points.
    """
    series: dict[str, list[Point]] = {label: [] for label in UST_TENORS.values()}
    for row in csv.DictReader(lines):
        valid_date = datetime.strptime(row["Date"], "%m/%d/%Y").date().isoformat()
        for column, label in UST_TENORS.items():
            if row.get(column):
                series[label].append((valid_date, float(row[column])))
    return series


def fetch_ust_history(last_year: int) -> dict[str, list[Point]]:
    """All published values per tenor from 1990 to ``last_year``, oldest first.

    One request per year, ``UST_PAUSE_SECONDS`` apart, one attempt each (no retry).
    """
    series: dict[str, list[Point]] = {label: [] for label in UST_TENORS.values()}
    for index, url in enumerate(ust_year_urls(last_year)):
        if index:
            time.sleep(UST_PAUSE_SECONDS)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            text = io.TextIOWrapper(response, encoding="utf-8-sig")
            for label, points in parse_ust_csv(text).items():
                series[label] += points
    return {label: sorted(points) for label, points in series.items()}


def daily_changes_bp(points: list[Point]) -> list[tuple[str, float]]:
    """Absolute change against the previous valid date with a value, in basis points."""
    return [(b[0], abs(b[1] - a[1]) * 100) for a, b in itertools.pairwise(points)]


def percentile(values: list[float], share: float) -> float:
    """Linear-interpolated percentile, as used in the methodology note."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * share
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Command line options; ``--curve`` defaults to ``ecb-aaa-spot`` and does not apply to ust."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("access", "ecb", "ust"), default="access")
    parser.add_argument("--access-url", default="http://localhost:8000")
    parser.add_argument("--curve", default=None)
    args = parser.parse_args(argv)
    if args.source == "ust":
        if args.curve is not None:
            parser.error(
                "--source ust reads the Treasury curve; --curve does not apply"
            )
        return args
    args.curve = args.curve or "ecb-aaa-spot"
    if args.source == "ecb" and args.curve not in ECB_INSTRUMENTS:
        parser.error(f"--source ecb needs --curve one of: {', '.join(ECB_INSTRUMENTS)}")
    return args


def load_history(args: argparse.Namespace) -> dict[str, list[Point]]:
    """Values per maturity or tenor, oldest first, from the source named in ``args``."""
    if args.source == "ecb":
        return fetch_ecb_history(args.curve)
    if args.source == "ust":
        return fetch_ust_history(date.today().year)
    return {
        maturity: fetch_series(args.access_url, args.curve, maturity)
        for maturity in MATURITIES
    }


def main() -> None:
    args = parse_args()
    history = load_history(args)
    if args.source != "access":
        first = min(points[0][0] for points in history.values() if points)
        last = max(points[-1][0] for points in history.values() if points)
        print(f"history: {first} to {last}")

    all_changes: list[tuple[str, str, float]] = []
    print(
        "maturity  values  first       min %    max %   p50 bp  p99 bp  p99.9 bp  max bp"
    )
    for maturity, points in history.items():
        if not points:
            continue
        changes = daily_changes_bp(points)
        sizes = [size for _, size in changes]
        values = [value for _, value in points]
        all_changes += [(day, maturity, size) for day, size in changes]
        print(
            f"{maturity:8}  {len(points):6}  {points[0][0]}  {min(values):7.3f}  {max(values):7.3f}"
            f"  {percentile(sizes, 0.5):6.1f}  {percentile(sizes, 0.99):6.1f}"
            f"  {percentile(sizes, 0.999):8.1f}  {max(sizes):6.1f}"
        )

    sizes = [size for _, _, size in all_changes]
    print(
        f"\nall maturities: {len(sizes)} daily changes, p99 {percentile(sizes, 0.99):.1f} bp, "
        f"p99.9 {percentile(sizes, 0.999):.1f} bp, max {max(sizes):.1f} bp"
    )
    for threshold in CANDIDATE_JUMPS_BP:
        hits = [
            (day, maturity) for day, maturity, size in all_changes if size > threshold
        ]
        days = sorted({day for day, _ in hits})
        years = sorted({day[:4] for day in days})
        print(
            f"> {threshold} bp: {len(hits)} values on {len(days)} days "
            f"({len(hits) / len(sizes):.3%} of changes); years {', '.join(years)}"
        )


if __name__ == "__main__":
    main()
