"""Download HSL city bike trips (Helsinki + Espoo) and load them to the raw layer.

Source: City bike stations' Origin-Destination (OD) data, HSL / City Bike Finland,
CC BY 4.0. Monthly files: https://dev.hsl.fi/citybikes/od-trips-YYYY/YYYY-MM.csv

Examples:
    python ingestion/trips.py --year 2025                      # Apr-Oct 2025 -> Snowflake
    python ingestion/trips.py --year 2025 --months 5 6         # only May and June
    python ingestion/trips.py --year 2024 --target duckdb      # local DuckDB instead
    python ingestion/trips.py --year 2025 --skip-download      # reuse cached files
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LANDING_DIR, RAW_DIR, TRIP_COLUMNS, load_to_duckdb, load_to_snowflake  # noqa: E402

BASE_URL = "https://dev.hsl.fi/citybikes/od-trips-{year}/{year}-{month:02d}.csv"

# Published English headers -> our column names. Matching ignores case and spaces.
HEADER_MAP = {
    "departure": "departure",
    "return": "return_time",
    "departurestationid": "departure_station_id",
    "departurestationname": "departure_station_name",
    "returnstationid": "return_station_id",
    "returnstationname": "return_station_name",
    "covereddistance(m)": "covered_distance_m",
    "duration(sec.)": "duration_sec",
}


def _key(header: str) -> str:
    return "".join(header.lower().split()).replace("﻿", "")


def download(year: int, month: int) -> Path | None:
    """Download one month to data/raw/trips/. Returns None if HSL has no file (404)."""
    target = RAW_DIR / "trips" / f"{year}-{month:02d}.csv"
    if target.exists() and target.stat().st_size > 0:
        print(f"  cached: {target.name}")
        return target
    url = BASE_URL.format(year=year, month=month)
    print(f"  downloading {url}")
    resp = requests.get(url, timeout=300)
    if resp.status_code == 404:
        print("  no file for this month (404), skipping")
        return None
    resp.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(resp.content)
    print(f"  saved {target.stat().st_size / 1e6:.1f} MB")
    return target


def normalise(raw_file: Path) -> Path:
    """Read any delimiter / encoding, rename headers, write a fixed-schema .csv.gz."""
    data = raw_file.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"Could not decode {raw_file}")

    delimiter = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t").delimiter
    df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)

    rename = {}
    for col in df.columns:
        if _key(col) in HEADER_MAP:
            rename[col] = HEADER_MAP[_key(col)]
    df = df.rename(columns=rename)
    missing = [c for c in TRIP_COLUMNS if c != "source_file" and c not in df.columns]
    if missing:
        raise ValueError(
            f"{raw_file.name}: could not find columns {missing}. "
            f"Headers in file: {list(df.columns)}. Add them to HEADER_MAP."
        )

    out = LANDING_DIR / f"trips_{raw_file.stem}.csv.gz"
    df["source_file"] = out.name
    out.parent.mkdir(parents=True, exist_ok=True)
    df[TRIP_COLUMNS].to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})  # same input -> identical bytes, so COPY INTO skips reloads
    print(f"  normalised {len(df):,} rows -> {out.name}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--months", type=int, nargs="+", default=list(range(4, 11)),
                        help="Months to load (default 4-10; months without a file are skipped)")
    parser.add_argument("--target", choices=["snowflake", "duckdb"], default="snowflake")
    parser.add_argument("--skip-download", action="store_true", help="Only use files already in data/raw")
    args = parser.parse_args()

    landing_files = []
    for month in args.months:
        print(f"{args.year}-{month:02d}")
        raw = RAW_DIR / "trips" / f"{args.year}-{month:02d}.csv"
        if not args.skip_download:
            raw = download(args.year, month)
        if raw is None or not raw.exists():
            continue
        landing_files.append(normalise(raw))

    if not landing_files:
        print("Nothing to load.")
        return
    print(f"Loading {len(landing_files)} file(s) to {args.target} ...")
    if args.target == "snowflake":
        load_to_snowflake(landing_files, "trips", TRIP_COLUMNS, stage_dir="trips")
    else:
        load_to_duckdb(landing_files, "trips", TRIP_COLUMNS)
    print("Done.")


if __name__ == "__main__":
    main()
