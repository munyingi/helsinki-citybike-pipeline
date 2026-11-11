"""Download daily weather from the Finnish Meteorological Institute (FMI) open data.

Station: Helsinki Kaisaniemi (fmisid 100971), the city-centre station used in
earlier Helsinki cycling studies. No API key needed. Licence: CC BY 4.0.

Parameters (daily):
    rrday  precipitation mm  (-1 means "it did not rain at all", per FMI)
    tday   mean temperature C
    tmin   minimum temperature C
    tmax   maximum temperature C
    snow   snow depth cm

Examples:
    python ingestion/weather.py --start 2025-04-01 --end 2025-10-31
    python ingestion/weather.py --start 2021-01-01 --end 2025-12-31 --target duckdb
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LANDING_DIR, RAW_DIR, WEATHER_COLUMNS, load_to_duckdb, load_to_snowflake  # noqa: E402

WFS_URL = "https://opendata.fmi.fi/wfs"
STORED_QUERY = "fmi::observations::weather::daily::simple"
PARAMS = "rrday,tday,tmin,tmax,snow"
CHUNK_DAYS = 31  # small requests stay well inside FMI's per-request limits


def _local(tag: str) -> str:
    """'{namespace}Time' -> 'Time' so parsing does not depend on namespace URIs."""
    return tag.rsplit("}", 1)[-1]


def parse_simple_xml(xml_bytes: bytes) -> list[dict]:
    """Parse an FMI 'simple' WFS response into rows of (obs_date, fmisid, parameter, value)."""
    root = ET.fromstring(xml_bytes)
    if _local(root.tag) == "ExceptionReport":
        texts = [el.text for el in root.iter() if _local(el.tag) == "ExceptionText" and el.text]
        raise RuntimeError("FMI error: " + " | ".join(texts))
    rows = []
    for element in root.iter():
        if _local(element.tag) != "BsWfsElement":
            continue
        fields = {_local(child.tag): (child.text or "").strip() for child in element}
        rows.append(
            {
                "obs_date": fields.get("Time", "")[:10],  # '2025-06-01T00:00:00Z' -> '2025-06-01'
                "parameter": fields.get("ParameterName", ""),
                "value": fields.get("ParameterValue", ""),
            }
        )
    return rows


def fetch(start: date, end: date, fmisid: int) -> list[dict]:
    rows = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), end)
        cache = RAW_DIR / "weather" / f"fmi_{fmisid}_{cursor}_{chunk_end}.xml"
        if cache.exists():
            content = cache.read_bytes()
        else:
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "getFeature",
                "storedquery_id": STORED_QUERY,
                "fmisid": fmisid,
                "starttime": f"{cursor}T00:00:00Z",
                "endtime": f"{chunk_end}T00:00:00Z",
                "parameters": PARAMS,
            }
            print(f"  FMI {cursor} -> {chunk_end}")
            resp = requests.get(WFS_URL, params=params, timeout=120)
            if resp.status_code >= 400:
                parse_simple_xml(resp.content)  # raises with FMI's own error text if present
                resp.raise_for_status()
            content = resp.content
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(content)
        chunk_rows = parse_simple_xml(content)
        if not chunk_rows:
            print(f"  warning: no observations for {cursor} -> {chunk_end}")
        rows.extend(chunk_rows)
        cursor = chunk_end + timedelta(days=1)
    for r in rows:
        r["fmisid"] = str(fmisid)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--fmisid", type=int, default=100971)
    parser.add_argument("--target", choices=["snowflake", "duckdb"], default="snowflake")
    args = parser.parse_args()

    rows = fetch(args.start, args.end, args.fmisid)
    if not rows:
        print("No weather rows returned; check dates and station id.")
        return
    out = LANDING_DIR / f"weather_{args.fmisid}_{args.start}_{args.end}.csv.gz"
    df = pd.DataFrame(rows)
    df["source_file"] = out.name
    out.parent.mkdir(parents=True, exist_ok=True)
    df[WEATHER_COLUMNS].to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})  # same input -> identical bytes, so COPY INTO skips reloads
    days = df["obs_date"].nunique()
    print(f"  {len(df):,} observations for {days} days -> {out.name}")

    if args.target == "snowflake":
        load_to_snowflake([out], "weather_daily", WEATHER_COLUMNS, stage_dir="weather")
    else:
        load_to_duckdb([out], "weather_daily", WEATHER_COLUMNS)
    print("Done.")


if __name__ == "__main__":
    main()
