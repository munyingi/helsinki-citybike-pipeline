"""Helsinki & Espoo City Bikes dashboard.

Reads the Parquet files written by scripts/export_marts.py, so it keeps working
after the Snowflake trial ends (and can be deployed to Streamlit Community Cloud).

Run locally:
    streamlit run dashboard/app.py
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "exports"

st.set_page_config(page_title="Helsinki City Bikes", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    path = DATA / f"{name}.parquet"
    if not path.exists():
        st.error(f"Missing {path.name}. Run: python scripts/export_marts.py")
        st.stop()
    return pd.read_parquet(path)


daily = load("agg_daily_trips")
hourly = load("agg_hourly_trips")
stations = load("dim_station")
station_daily = load("agg_station_daily")
quality = load("quality_trip_status")

daily["trip_date"] = pd.to_datetime(daily["trip_date"])
hourly["trip_date"] = pd.to_datetime(hourly["trip_date"])
station_daily["trip_date"] = pd.to_datetime(station_daily["trip_date"])

st.title("Helsinki & Espoo City Bikes")
st.caption(
    "Data: City bike OD trips, HSL / City Bike Finland (CC BY 4.0); "
    "weather: Finnish Meteorological Institute, Helsinki Kaisaniemi (CC BY 4.0). "
    "Trips shorter than 10 s or 10 m, or longer than 5 h, are excluded."
)

years = sorted(daily["year"].dropna().astype(int).unique())
chosen = st.sidebar.multiselect("Years", years, default=years)
d = daily[daily["year"].isin(chosen)]
h = hourly[hourly["trip_date"].dt.year.isin(chosen)]
sd = station_daily[station_daily["trip_date"].dt.year.isin(chosen)]

tab_overview, tab_weather, tab_calendar, tab_stations, tab_quality = st.tabs(
    ["Overview", "Weather", "Calendar", "Stations", "Data quality"]
)

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trips", f"{int(d['trips'].sum()):,}")
    c2.metric("Avg trips per day", f"{d['trips'].mean():,.0f}")
    c3.metric("Median trip (min)", f"{d['median_duration_min'].median():.1f}")
    c4.metric("Distance ridden (km)", f"{d['total_distance_km'].sum():,.0f}")
    st.subheader("Trips per day")
    st.altair_chart(
        alt.Chart(d).mark_line().encode(
            x=alt.X("trip_date:T", title=None),
            y=alt.Y("trips:Q", title="Trips"),
                        detail="year(trip_date):O",
            tooltip=["trip_date:T", "trips:Q", "temp_mean_c:Q", "precipitation_mm:Q"],
        ),
        width="stretch",
    )

with tab_weather:
    rainy = d.dropna(subset=["is_rainy_day"])
    if not rainy.empty:
        comp = rainy.groupby("is_rainy_day")["trips"].mean()
        if True in comp.index and False in comp.index:
            change = 100 * (comp[True] / comp[False] - 1)
            st.subheader(f"Rainy days (1 mm or more) average {change:+.0f}% trips vs dry days")
    st.altair_chart(
        alt.Chart(d.dropna(subset=["temp_mean_c"])).mark_circle(opacity=0.5).encode(
            x=alt.X("temp_mean_c:Q", title="Mean temperature (C)"),
            y=alt.Y("trips:Q", title="Trips per day"),
            color=alt.Color("is_rainy_day:N", title="Rainy day"),
            tooltip=["trip_date:T", "trips:Q", "temp_mean_c:Q", "precipitation_mm:Q"],
        ),
        width="stretch",
    )
    st.caption("Each dot is one day. Weekends and holidays are mixed in; see the Calendar tab.")

with tab_calendar:
    by_type = d.assign(
        day_type=d.apply(
            lambda r: r["special_day_name"] if pd.notna(r["special_day_name"])
            else r["holiday_name"] if pd.notna(r["holiday_name"])
            else ("Weekend" if r["is_weekend"] else "Working day"),
            axis=1,
        )
    )
    summary = (by_type.groupby("day_type")["trips"].mean().sort_values().reset_index())
    st.subheader("Average trips by type of day")
    st.altair_chart(
        alt.Chart(summary).mark_bar().encode(
            x=alt.X("trips:Q", title="Average trips per day"),
            y=alt.Y("day_type:N", sort="-x", title=None),
        ),
        width="stretch",
    )
    st.subheader("Hourly profile: working days vs days off")
    prof = h.groupby(["departure_hour", "is_day_off"])["trips"].sum().reset_index()
    days = h.groupby("is_day_off")["trip_date"].nunique().rename("n_days").reset_index()
    prof = prof.merge(days, on="is_day_off")
    prof["avg_trips"] = prof["trips"] / prof["n_days"]
    prof["day"] = prof["is_day_off"].map({True: "Day off", False: "Working day"})
    st.altair_chart(
        alt.Chart(prof).mark_line(point=True).encode(
            x=alt.X("departure_hour:O", title="Hour of departure"),
            y=alt.Y("avg_trips:Q", title="Average trips"),
            color=alt.Color("day:N", title=None),
        ),
        width="stretch",
    )

with tab_stations:
    totals = (
        sd.groupby("station_id")[["departures", "arrivals", "net_flow"]].sum().reset_index()
        .merge(stations[["station_id", "station_name"]], on="station_id", how="left")
    )
    left, right = st.columns(2)
    left.subheader("Busiest stations (departures)")
    left.dataframe(totals.nlargest(15, "departures")[["station_name", "departures", "arrivals"]],
                   hide_index=True, width="stretch")
    right.subheader("Stations that drain most (arrivals - departures)")
    right.dataframe(totals.nsmallest(15, "net_flow")[["station_name", "net_flow"]],
                    hide_index=True, width="stretch")
    st.caption("A draining station needs bikes brought in by the operator.")

with tab_quality:
    st.subheader("Rows per load file and why rows were rejected")
    st.dataframe(quality.sort_values(["source_file", "quality_status"]),
                 hide_index=True, width="stretch")
