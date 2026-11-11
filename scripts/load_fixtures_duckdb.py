"""Load the synthetic fixtures into DuckDB through the real parsing code (used by CI).

Usage:
    python scripts/load_fixtures_duckdb.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))

from common import LANDING_DIR, TRIP_COLUMNS, WEATHER_COLUMNS, load_to_duckdb  # noqa: E402
from trips import normalise  # noqa: E402
from weather import parse_simple_xml  # noqa: E402

FIXTURES = ROOT / "data" / "fixtures"

trips_file = normalise(FIXTURES / "2025-05.csv")
load_to_duckdb([trips_file], "trips", TRIP_COLUMNS)

rows = parse_simple_xml((FIXTURES / "fmi_sample.xml").read_bytes())
weather_file = LANDING_DIR / "weather_fixture.csv.gz"
df = pd.DataFrame(rows)
df["fmisid"] = "100971"
df["source_file"] = weather_file.name
df[WEATHER_COLUMNS].to_csv(weather_file, index=False, compression={"method": "gzip", "mtime": 0})
load_to_duckdb([weather_file], "weather_daily", WEATHER_COLUMNS)
