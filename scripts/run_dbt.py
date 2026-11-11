"""Run dbt with the settings from .env (works the same on Windows, macOS and Linux).
Note: this file's name must not start with "dbt_" (dbt imports such modules as plugins).

Usage (from the repo root):
    python scripts/run_dbt.py debug                     # test the Snowflake connection
    python scripts/run_dbt.py build                     # seeds + models + tests on Snowflake
    python scripts/run_dbt.py build --target duckdb     # same on local DuckDB
    python scripts/run_dbt.py docs generate
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))
from common import load_dotenv  # noqa: E402

load_dotenv()
os.environ.setdefault("DUCKDB_PATH", str(ROOT / "data" / "citybike.duckdb"))
os.chdir(ROOT / "dbt")

from dbt.cli.main import dbtRunner  # noqa: E402

args = sys.argv[1:] or ["build"]
if "--profiles-dir" not in args:
    args += ["--profiles-dir", "."]
result = dbtRunner().invoke(args)
sys.exit(0 if result.success else 1)
