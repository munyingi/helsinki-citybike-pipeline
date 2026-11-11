"""Shared helpers: settings, paths, Snowflake and DuckDB connections, loading."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"          # files exactly as downloaded (cache)
LANDING_DIR = ROOT / "data" / "landing"  # normalised .csv.gz files ready to load
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", ROOT / "data" / "citybike.duckdb"))

TRIP_COLUMNS = [
    "departure",
    "return_time",
    "departure_station_id",
    "departure_station_name",
    "return_station_id",
    "return_station_name",
    "covered_distance_m",
    "duration_sec",
    "source_file",
]
WEATHER_COLUMNS = ["obs_date", "fmisid", "parameter", "value", "source_file"]


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader so we need no extra package. Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def snowflake_connect():
    """Connect with key-pair auth (Snowflake blocks password-only service users)."""
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    load_dotenv()
    key_path = Path(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]).expanduser()
    if not key_path.is_absolute():
        key_path = ROOT / key_path
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ.get("SNOWFLAKE_USER", "DBT_USER"),
        private_key=private_key_der,
        role=os.environ.get("SNOWFLAKE_ROLE", "TRANSFORMER"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "CITYBIKE_WH"),
        database="CITYBIKE",
        schema="RAW",
    )


def load_to_snowflake(files: list[Path], table: str, columns: list[str], stage_dir: str) -> None:
    """PUT files to the internal stage, then COPY INTO the raw table.

    COPY INTO remembers which staged files it has already loaded (for 64 days),
    so running this twice for the same month does not duplicate rows.
    """
    if not files:
        return
    conn = snowflake_connect()
    try:
        cur = conn.cursor()
        for f in files:
            cur.execute(
                f"PUT 'file://{f.resolve().as_posix()}' @landing/{stage_dir}/ "
                "AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
            )
        names = ", ".join(f"'{f.name}'" for f in files)
        cur.execute(
            f"COPY INTO {table} ({', '.join(columns)}) "
            f"FROM @landing/{stage_dir}/ FILES = ({names}) "
            "FILE_FORMAT = (FORMAT_NAME = csv_gz) ON_ERROR = ABORT_STATEMENT"
        )
        # One result row per file (file, status, rows_parsed, rows_loaded, ...),
        # or a single message row if every file was already loaded before.
        for row in cur.fetchall():
            print("  COPY:", " | ".join(str(v) for v in row[:4]))
    finally:
        conn.close()


def load_to_duckdb(files: list[Path], table: str, columns: list[str]) -> None:
    """Same contract as load_to_snowflake, for local runs and CI.

    Idempotent: rows from the same source file are deleted before re-insert.
    """
    import duckdb

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        col_defs = ", ".join(f"{c} VARCHAR" for c in columns)
        con.execute(
            f"CREATE TABLE IF NOT EXISTS raw.{table} ({col_defs}, "
            "loaded_at TIMESTAMP DEFAULT current_timestamp)"
        )
        for f in files:
            con.execute(f"DELETE FROM raw.{table} WHERE source_file = ?", [f.name])
            con.execute(
                f"INSERT INTO raw.{table} ({', '.join(columns)}) "
                f"SELECT {', '.join(columns)} FROM read_csv(?, header = true, all_varchar = true, "
                "compression = 'gzip')",
                [str(f)],
            )
            n = con.execute(f"SELECT count(*) FROM raw.{table} WHERE source_file = ?", [f.name]).fetchone()[0]
            print(f"  DuckDB: {f.name} -> raw.{table}: {n} rows")
    finally:
        con.close()
