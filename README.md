# Helsinki City Bike Pipeline

An end-to-end data engineering project on Helsinki and Espoo city bike trips:
Python ingestion, Snowflake, dbt, automated tests, CI and a Streamlit dashboard.

**Question:** how do weather, holidays and the calendar shape city bike use in Helsinki and Espoo?

![CI](https://github.com/munyingi/helsinki-citybike-pipeline/actions/workflows/ci.yml/badge.svg)

## Architecture

```
HSL trip CSVs ─┐                       ┌─ staging (views)  ─┐
               ├─ Python ─ stage ─ COPY INTO ─ raw ─ dbt ──┤                    ├─ Parquet ─ Streamlit
FMI weather ───┘   (normalise)                             └─ marts + quality ──┘
                                                 seeds: calendar, special days, official totals
```

- **Ingestion** (`ingestion/`): downloads monthly trip files and daily weather, normalises
  headers and delimiters, writes fixed-schema `.csv.gz`, then `PUT` + `COPY INTO` Snowflake.
  `COPY INTO` remembers loaded files, so re-running a month does not duplicate rows.
- **Warehouse** (`snowflake/01_setup.sql`): X-Small warehouse with 60 s auto-suspend,
  a 20-credit resource monitor, a least-privilege `TRANSFORMER` role and a key-pair service user.
- **Transformation** (`dbt/`): staging (typing, dedup, quality labels) → marts
  (`fct_trips`, `dim_station`, `dim_date`, daily/hourly/station aggregates) → quality tables.
  24 data tests, including custom generic tests.
- **Portability**: the same dbt project runs on DuckDB (`--target duckdb`), so the project
  keeps working for free after the Snowflake trial.
- **CI** (`.github/workflows/ci.yml`): every push loads synthetic fixtures through the real
  parsers, runs `dbt build` on DuckDB and smoke-tests the dashboard. No secrets needed.
- **Privacy**: only aggregates are exported or published, never trip-level rows.

## Quick start

Python 3.11 to 3.13.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/make_keypair.py       # then run the printed ALTER USER in Snowsight
cp .env.example .env                 # Windows: copy .env.example .env; then fill it in
```

1. Run `snowflake/01_setup.sql` in a Snowsight worksheet (paste your public key first).
2. Load data:
   ```bash
   python ingestion/trips.py --year 2025
   python ingestion/weather.py --start 2025-04-01 --end 2025-10-31
   ```
3. Transform and test: `python scripts/run_dbt.py build`
4. Export and view: `python scripts/export_marts.py` then `streamlit run dashboard/app.py`

Without Snowflake, add `--target duckdb` to steps 2 to 4.

## Data sources

| Data | Source | Licence |
|---|---|---|
| City bike trips (Helsinki + Espoo), 2021-2025 | HSL, City bike stations' Origin-Destination data, owned by City Bike Finland | CC BY 4.0 |
| Daily weather, Helsinki Kaisaniemi (fmisid 100971) | Finnish Meteorological Institute open data | CC BY 4.0 |
| Finnish public holidays | `holidays` Python package | MIT |

Definitions and limitations: [docs/metrics.md](docs/metrics.md).

## Next steps

- Incremental model for `fct_trips` and a snapshot of station names (SCD2)
- Station coordinates and city from HSL's station dataset, then a map
- Helsinki cyclist counter data (year-round) and the "did cycling decline?" question
- Spatial joins: population (Statistics Finland Paavo), universities, metro stations
- Next-day station risk model
- Rebuild the core on Microsoft Fabric
