"""Derive the plausibility thresholds of a curve from its full published history.

Reads every maturity's time series through the public access API of a running
stack (load the history first, e.g. ``task dev:seed START=2004-09-06``) and prints
the statistics the thresholds in
``docs/project/02-data-processing/01-plausibility-thresholds.md`` are based on:
the value range per maturity, the distribution of daily absolute changes, and how
often each candidate jump threshold would have been exceeded. The history is read
through the access API, or, with ``--source ecb``, in one request straight from the
ECB data API (no stack needed).

Usage: python3 src/scripts/plausibility_thresholds.py [--source access|ecb]
       [--access-url URL] [--curve ID]
Standard library only; no write access.
"""

import argparse
import csv
import io
import itertools
import json
import urllib.request
from datetime import date, timedelta

MATURITIES = ("3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
FIRST_VALID_DATE = date(2004, 9, 6)  # start of the ECB AAA spot curve series
MAX_RANGE_DAYS = 3650  # below the API's 3660-day limit per request
CANDIDATE_JUMPS_BP = (20, 25, 30, 40, 50)
ECB_URL = "https://data-api.ecb.europa.eu/service/data/YC"
ECB_INSTRUMENTS = {"ecb-aaa-spot": "G_N_A", "ecb-all-spot": "G_N_C"}
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("access", "ecb"), default="access")
    parser.add_argument("--access-url", default="http://localhost:8000")
    parser.add_argument("--curve", default="ecb-aaa-spot")
    args = parser.parse_args()
    if args.source == "ecb" and args.curve not in ECB_INSTRUMENTS:
        parser.error(f"--source ecb needs --curve one of: {', '.join(ECB_INSTRUMENTS)}")

    history = fetch_ecb_history(args.curve) if args.source == "ecb" else None
    if history is not None:
        print(f"history: {history['3M'][0][0]} to {history['3M'][-1][0]}")

    all_changes: list[tuple[str, str, float]] = []
    print(
        "maturity  values  first       min %    max %   p50 bp  p99 bp  p99.9 bp  max bp"
    )
    for maturity in MATURITIES:
        if history is not None:
            points = history[maturity]
        else:
            points = fetch_series(args.access_url, args.curve, maturity)
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
