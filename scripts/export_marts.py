"""Export the publishable (aggregated) tables to Parquet for the dashboard.

Only aggregates leave the warehouse: no trip-level rows are exported (privacy).
Run this BEFORE the Snowflake trial ends; the dashboard then works without Snowflake.

Usage:
    python scripts/export_marts.py --target snowflake
    python scripts/export_marts.py --target duckdb
"""
import argparse
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))
from common import DUCKDB_PATH, snowflake_connect  # noqa: E402

EXPORT_DIR = ROOT / "data" / "exports"
TABLES = {
    "agg_daily_trips": "marts",
    "agg_hourly_trips": "marts",
    "agg_station_daily": "marts",
    "dim_station": "marts",
    "agg_trip_types": "marts",
    "agg_od_pairs": "marts",
    "agg_city_flows": "marts",
    "dim_date": "marts",
    "quality_trip_status": "quality",
    "quality_reconciliation": "quality",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["snowflake", "duckdb"], default="snowflake")
    args = parser.parse_args()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    if args.target == "snowflake":
        conn = snowflake_connect()
        cur = conn.cursor()
        for table, schema in TABLES.items():
            cur.execute(f"SELECT * FROM CITYBIKE.{schema}.{table}")
            cols = [c[0].lower() for c in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
            # Snowflake returns NUMBER(p, s>0) as Python Decimal; make those plain floats.
            for col in df.columns:
                if df[col].map(lambda v: isinstance(v, Decimal)).any():
                    df[col] = pd.to_numeric(df[col])
            df.to_parquet(EXPORT_DIR / f"{table}.parquet", index=False)
            print(f"{table}: {len(df):,} rows")
        conn.close()
    else:
        import duckdb

        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        for table, schema in TABLES.items():
            out = (EXPORT_DIR / f"{table}.parquet").as_posix()
            con.execute(f"COPY (SELECT * FROM {schema}.{table}) TO '{out}' (FORMAT parquet)")
            n = con.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0]
            print(f"{table}: {n:,} rows")
        con.close()
    print(f"Exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
