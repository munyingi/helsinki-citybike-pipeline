"""Helsinki & Espoo City Bikes dashboard.

Reads the Parquet files written by scripts/export_marts.py, so it keeps working
after the Snowflake trial ends (and can be deployed to Streamlit Community Cloud).

Run locally:
    streamlit run dashboard/app.py
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "exports"
MONTHS = {4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct"}
COMPARABLE_BAND = "4: 15-20 C"

st.set_page_config(page_title="Helsinki City Bikes", layout="wide")


@st.cache_data
def _read(path: str, mtime: float) -> pd.DataFrame:
    # mtime is part of the cache key, so a fresh export is picked up without a restart.
    return pd.read_parquet(path)


def load(name: str) -> pd.DataFrame:
    path = DATA / f"{name}.parquet"
    if not path.exists():
        st.error(f"Missing {path.name}. Run: python scripts/export_marts.py")
        st.stop()
    return _read(str(path), path.stat().st_mtime)


def as_bool(s: pd.Series) -> pd.Series:
    """Booleans can arrive as bool, object or nullable; keep missing as NA."""
    return s.map(lambda v: pd.NA if pd.isna(v) else bool(v)).astype("boolean")


def pct(a: float, b: float) -> float:
    return float("nan") if not b or pd.isna(a) or pd.isna(b) else 100 * (a / b - 1)


# ---------------------------------------------------------------- data
daily = load("agg_daily_trips").copy()
hourly = load("agg_hourly_trips").copy()
stations = load("dim_station")
station_daily = load("agg_station_daily").copy()
quality = load("quality_trip_status")


def load_optional(name: str) -> pd.DataFrame | None:
    path = DATA / f"{name}.parquet"
    return _read(str(path), path.stat().st_mtime) if path.exists() else None


trip_types = load_optional("agg_trip_types")
od_pairs = load_optional("agg_od_pairs")
city_flows = load_optional("agg_city_flows")
HAS_GEO = {"city", "lat", "lon"}.issubset(stations.columns)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

daily["trip_date"] = pd.to_datetime(daily["trip_date"])
hourly["trip_date"] = pd.to_datetime(hourly["trip_date"])
station_daily["trip_date"] = pd.to_datetime(station_daily["trip_date"])
for col in ["trips", "temp_mean_c", "precipitation_mm", "median_duration_min",
            "avg_distance_km", "total_distance_km", "active_stations", "year", "month"]:
    if col in daily:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")
for col in ["is_day_off", "is_weekend", "is_rainy_day"]:
    daily[col] = as_bool(daily[col])
hourly["is_day_off"] = as_bool(hourly["is_day_off"])
hourly["trips"] = pd.to_numeric(hourly["trips"], errors="coerce")
for col in ["departures", "arrivals", "net_flow"]:
    station_daily[col] = pd.to_numeric(station_daily[col], errors="coerce")

daily["label"] = np.where(
    daily["special_day_name"].notna(), daily["special_day_name"],
    np.where(daily["holiday_name"].notna(), daily["holiday_name"], None),
)

# ---------------------------------------------------------------- header
st.title("Helsinki & Espoo City Bikes, 2021 to 2025")
st.markdown(
    "**The question:** what makes people ride city bikes in Helsinki and Espoo, "
    "and what does that mean for the people who run, plan and use the system?"
)
st.caption(
    "Data: City bike OD trips, HSL / City Bike Finland (CC BY 4.0); weather: Finnish "
    "Meteorological Institute, Helsinki Kaisaniemi (CC BY 4.0). Trips shorter than 10 s "
    "or 10 m, or longer than 5 h, are excluded. The season runs April to October."
)

years = sorted(daily["year"].dropna().astype(int).unique())
chosen = st.sidebar.multiselect("Years", years, default=years)
st.sidebar.caption("All tabs follow this filter.")
d = daily[daily["year"].isin(chosen)]
h = hourly[hourly["trip_date"].dt.year.isin(chosen)]
sd = station_daily[station_daily["trip_date"].dt.year.isin(chosen)]
if d.empty:
    st.warning("Choose at least one year.")
    st.stop()

work = d[d["is_day_off"] == False]  # noqa: E712  (nullable boolean)
n_days = d["trip_date"].nunique()

# Headline numbers used in several tabs.
rain_known = work.dropna(subset=["is_rainy_day"])
rain_effect = pct(rain_known.loc[rain_known["is_rainy_day"] == True, "trips"].mean(),   # noqa: E712
                  rain_known.loc[rain_known["is_rainy_day"] == False, "trips"].mean())  # noqa: E712
temp_known = work.dropna(subset=["temp_mean_c"])
slope = (np.polyfit(temp_known["temp_mean_c"], temp_known["trips"], 1)[0]
         if len(temp_known) > 2 and temp_known["temp_mean_c"].nunique() > 1 else float("nan"))
dayoff_effect = pct(d.loc[d["is_day_off"] == True, "trips"].mean(),   # noqa: E712
                    d.loc[d["is_day_off"] == False, "trips"].mean())  # noqa: E712

tabs = st.tabs(["Key findings", "Trends by year", "Weather", "Calendar", "Trip types",
                "Stations and map", "Routes", "Helsinki vs Espoo", "Estimate a day", "Data quality"])

# ================================================================ Key findings
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trips", f"{int(d['trips'].sum()):,}")
    c2.metric("Average trips per day", f"{d['trips'].mean():,.0f}")
    c3.metric("Median trip", f"{d['median_duration_min'].median():.1f} min")
    c4.metric("Distance ridden", f"{d['total_distance_km'].sum():,.0f} km")

    st.subheader("What the data says")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Each extra 1 °C", f"{slope:+,.0f} trips/day" if pd.notna(slope) else "n/a")
    k2.metric("Rainy working day", f"{rain_effect:+.0f}%" if pd.notna(rain_effect) else "n/a")
    k3.metric("Weekend or holiday", f"{dayoff_effect:+.0f}%" if pd.notna(dayoff_effect) else "n/a")
    busiest = d.loc[d["trips"].idxmax()]
    k4.metric("Busiest day", f"{int(busiest['trips']):,}",
              busiest["trip_date"].strftime("%a %d %b %Y"), delta_color="off")

    st.markdown(
        "- **Warmth is the biggest driver.** Trips climb steadily with temperature.\n"
        "- **Rain matters on its own**, not just because rainy days are colder: "
        "see the Weather tab, which compares days of the same temperature.\n"
        "- **Working days are busier** and have commute peaks; days off have one afternoon peak.\n"
        "- **Bikes drift downhill and into the centre**, so a few stations need bikes "
        "brought back every day (Stations tab)."
    )

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

    with st.expander("What this means for you"):
        st.markdown(
            "- **Riders and residents:** expect the fullest stations on warm, dry working days "
            "around 8:00 and 16:00 to 17:00, and empty docks at stations like Pasila in the evening.\n"
            "- **Operators and businesses:** demand can be planned from the weather forecast and the "
            "calendar (Estimate a day tab); rebalancing effort concentrates on a handful of stations.\n"
            "- **City planners:** a cold or wet season can cut use by a fifth, so judge long-term trends "
            "on comparable days, not raw totals (Trends by year tab).\n"
            "- **Researchers:** all models, tests and data-quality decisions are in the GitHub repo; "
            "results are associations, not causal estimates."
        )

# ================================================================ Trends by year
with tabs[1]:
    st.markdown(
        "**Question:** is city bike use growing or shrinking, and are changes about people "
        "or just the weather?"
    )
    season = d[d["month"].between(5, 9)]
    comparable = work[(work["is_rainy_day"] == False) & (work["temp_band"] == COMPARABLE_BAND)]  # noqa: E712
    yearly = (
        d.groupby("year").agg(trips=("trips", "sum"), days=("trips", "size"))
        .join(season.groupby("year").agg(
            per_day_may_sep=("trips", "mean"),
            mean_temp_c=("temp_mean_c", "mean"),
            rainy_share=("is_rainy_day", lambda s: s.astype("float").mean()),
            median_trip_min=("median_duration_min", "median"),
            avg_trip_km=("avg_distance_km", "mean"),
        ))
        .join(comparable.groupby("year")["trips"].mean().rename("comparable_day"))
        .reset_index()
    )
    yearly["year"] = yearly["year"].astype(int)
    st.dataframe(
        yearly.rename(columns={
            "year": "Year", "trips": "Trips", "days": "Days",
            "per_day_may_sep": "Trips/day May-Sep", "mean_temp_c": "Mean temp May-Sep (°C)",
            "rainy_share": "Rainy days May-Sep", "comparable_day": "Trips on a comparable day",
            "median_trip_min": "Median trip (min)", "avg_trip_km": "Avg trip (km)",
        }),
        hide_index=True, width="stretch",
        column_config={
            "Trips": st.column_config.NumberColumn(format="%d"),
            "Trips/day May-Sep": st.column_config.NumberColumn(format="%d"),
            "Mean temp May-Sep (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Rainy days May-Sep": st.column_config.NumberColumn(format="percent"),
            "Trips on a comparable day": st.column_config.NumberColumn(format="%d"),
            "Median trip (min)": st.column_config.NumberColumn(format="%.1f"),
            "Avg trip (km)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.caption(
        "A **comparable day** is a dry working day with a mean temperature of 15 to 20 °C. "
        "Comparing those days removes most of the weather, so differences point to changes in demand."
    )

    st.subheader("Each season, month by month")
    monthly = d.groupby(["year", "month"])["trips"].mean().reset_index()
    monthly["month_name"] = monthly["month"].map(MONTHS)
    monthly["year"] = monthly["year"].astype(int).astype(str)
    st.altair_chart(
        alt.Chart(monthly).mark_line(point=True).encode(
            x=alt.X("month_name:N", sort=list(MONTHS.values()), title=None),
            y=alt.Y("trips:Q", title="Average trips per day"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", "month_name:N", alt.Tooltip("trips:Q", format=",.0f")],
        ),
        width="stretch",
    )

    st.subheader("Notable changes")
    m = (d.groupby(["year", "month"])
         .agg(trips=("trips", "mean"), temp=("temp_mean_c", "mean"),
              rainy=("is_rainy_day", lambda s: s.astype("float").mean()),
              open_stations=("active_stations", "mean"))
         .reset_index())
    if m["year"].nunique() > 1:
        others = []
        for _, r in m.iterrows():
            rest = m[(m["month"] == r["month"]) & (m["year"] != r["year"])]
            others.append((rest["trips"].mean(), rest["temp"].mean(), rest["rainy"].mean(),
                           rest["open_stations"].mean()))
        m[["trips_other", "temp_other", "rainy_other", "stations_other"]] = pd.DataFrame(
            others, index=m.index)
        m["diff_pct"] = 100 * (m["trips"] / m["trips_other"] - 1)
        m = m.dropna(subset=["diff_pct"])
        notable = pd.concat([m.nlargest(3, "diff_pct"), m.nsmallest(3, "diff_pct")])
        lines = []
        for _, r in notable.iterrows():
            why = []
            if pd.notna(r["temp"]) and pd.notna(r["temp_other"]):
                dt = r["temp"] - r["temp_other"]
                if abs(dt) >= 1:
                    why.append(f"{abs(dt):.1f} °C {'warmer' if dt > 0 else 'colder'} than usual")
            if pd.notna(r["rainy"]) and pd.notna(r["rainy_other"]):
                dr = 100 * (r["rainy"] - r["rainy_other"])
                if abs(dr) >= 10:
                    why.append(f"rain on {100 * r['rainy']:.0f}% of days vs {100 * r['rainy_other']:.0f}% usually")
            if pd.notna(r["open_stations"]) and r["stations_other"]:
                ds = 100 * (r["open_stations"] / r["stations_other"] - 1)
                if abs(ds) >= 10:
                    why.append(f"{abs(ds):.0f}% {'more' if ds > 0 else 'fewer'} stations in use")
            reason = "; ".join(why) if why else "weather close to normal, so likely other causes"
            lines.append(
                f"- **{MONTHS.get(int(r['month']), r['month'])} {int(r['year'])}:** "
                f"{r['trips']:,.0f} trips/day, {r['diff_pct']:+.0f}% vs the same month in other years "
                f"({reason})."
            )
        st.markdown("\n".join(lines))
        st.caption("Compared with the average of the same month in the other selected years.")
    else:
        st.info("Select two or more years to see notable changes.")

# ================================================================ Weather
with tabs[2]:
    st.markdown(
        "**Question:** how much do temperature and rain change demand? "
        "Working days only, so weekends and holidays do not blur the picture."
    )
    st.subheader("Rain at the same temperature")
    band = (work.dropna(subset=["is_rainy_day", "temp_band"])
            .groupby(["temp_band", "is_rainy_day"])["trips"].agg(["mean", "size"]).reset_index())
    band["day"] = band["is_rainy_day"].map({True: "Rainy (1 mm+)", False: "Dry"})
    band["band"] = band["temp_band"].str.split(": ").str[-1]
    st.altair_chart(
        alt.Chart(band).mark_bar().encode(
            x=alt.X("band:N", title="Mean temperature", sort=sorted(band["band"].unique(),
                    key=lambda b: band.loc[band["band"] == b, "temp_band"].iloc[0])),
            xOffset="day:N",
            y=alt.Y("mean:Q", title="Average trips per working day"),
            color=alt.Color("day:N", title=None),
            tooltip=["band:N", "day:N", alt.Tooltip("mean:Q", format=",.0f"),
                     alt.Tooltip("size:Q", title="days")],
        ),
        width="stretch",
    )
    wide = band.pivot(index="band", columns="is_rainy_day", values="mean")
    if True in wide.columns and False in wide.columns:
        eff = (100 * (wide[True] / wide[False] - 1)).dropna()
        if not eff.empty:
            st.caption(
                f"Within the same temperature band, rain changes trips by {eff.min():+.0f}% to "
                f"{eff.max():+.0f}%. So rain has its own effect, not just through colder weather."
            )

    st.subheader("Heavier rain, fewer trips")
    rb = work.dropna(subset=["precipitation_mm"]).copy()
    rb["rain"] = pd.cut(rb["precipitation_mm"], [-1, 0.05, 1, 5, 10, 1000],
                        labels=["Dry", "Under 1 mm", "1-5 mm", "5-10 mm", "10 mm+"])
    rbs = rb.groupby("rain", observed=True)["trips"].agg(["mean", "size"]).reset_index()
    if not rbs.empty and (rbs["rain"] == "Dry").any():
        dry = rbs.loc[rbs["rain"] == "Dry", "mean"].iloc[0]
        rbs["vs_dry"] = 100 * (rbs["mean"] / dry - 1)
    else:
        rbs["vs_dry"] = np.nan
    st.altair_chart(
        alt.Chart(rbs).mark_bar().encode(
            x=alt.X("rain:N", sort=None, title="Daily rainfall"),
            y=alt.Y("mean:Q", title="Average trips per working day"),
            tooltip=["rain:N", alt.Tooltip("mean:Q", format=",.0f"),
                     alt.Tooltip("vs_dry:Q", title="% vs dry", format="+.0f"),
                     alt.Tooltip("size:Q", title="days")],
        ),
        width="stretch",
    )

    st.subheader("Every day: temperature vs trips")
    st.altair_chart(
        alt.Chart(d.dropna(subset=["temp_mean_c"])).mark_circle(opacity=0.5).encode(
            x=alt.X("temp_mean_c:Q", title="Mean temperature (°C)"),
            y=alt.Y("trips:Q", title="Trips per day"),
            color=alt.Color("is_rainy_day:N", title="Rainy day"),
            tooltip=["trip_date:T", "trips:Q", "temp_mean_c:Q", "precipitation_mm:Q"],
        ),
        width="stretch",
    )
    if pd.notna(slope):
        st.caption(f"On working days, each extra degree adds about {slope:,.0f} trips a day.")

# ================================================================ Calendar
with tabs[3]:
    st.markdown(
        "**Question:** do holidays and city events change how much people ride? "
        "Each holiday is compared with **ordinary days of the same kind in the same month**, "
        "so a June holiday is not flattered by June weather."
    )
    rows = []
    for _, r in d[d["label"].notna()].iterrows():
        base = d[(d["year"] == r["year"]) & (d["month"] == r["month"]) & d["label"].isna()
                 & (d["is_weekend"] == r["is_weekend"])]["trips"].mean()
        rows.append({"day": r["label"], "trips": r["trips"], "diff": pct(r["trips"], base)})
    if rows:
        hol = (pd.DataFrame(rows).groupby("day")
               .agg(diff=("diff", "mean"), trips=("trips", "mean"), n=("trips", "size"))
               .reset_index().dropna(subset=["diff"]))
        hol["direction"] = np.where(hol["diff"] >= 0, "Busier", "Quieter")
        st.subheader("Holidays and special days vs a normal day")
        st.altair_chart(
            alt.Chart(hol).mark_bar().encode(
                x=alt.X("diff:Q", title="% vs ordinary days in the same month"),
                y=alt.Y("day:N", sort="x", title=None),
                color=alt.Color("direction:N", title=None,
                                scale=alt.Scale(domain=["Busier", "Quieter"])),
                tooltip=["day:N", alt.Tooltip("diff:Q", format="+.0f", title="% vs normal"),
                         alt.Tooltip("trips:Q", format=",.0f", title="avg trips"),
                         alt.Tooltip("n:Q", title="days")],
            ),
            width="stretch",
        )
        st.caption("Each holiday happens once a year, so each bar rests on only a few days.")

    st.subheader("Day of the week")
    ordinary = d[d["label"].isna()]
    dow = ordinary.groupby("weekday_name")["trips"].agg(["mean", "size"]).reindex(WEEKDAYS).dropna().reset_index()
    if not dow.empty:
        st.altair_chart(
            alt.Chart(dow).mark_bar().encode(
                x=alt.X("weekday_name:N", sort=WEEKDAYS, title=None),
                y=alt.Y("mean:Q", title="Average trips per day"),
                tooltip=["weekday_name:N", alt.Tooltip("mean:Q", format=",.0f"),
                         alt.Tooltip("size:Q", title="days")],
            ),
            width="stretch",
        )
        top, low = dow.loc[dow["mean"].idxmax()], dow.loc[dow["mean"].idxmin()]
        st.caption(f"Holidays left out. Busiest: {top['weekday_name']} ({top['mean']:,.0f} a day); "
                   f"quietest: {low['weekday_name']} ({low['mean']:,.0f}), "
                   f"{pct(low['mean'], top['mean']):+.0f}%.")

    st.subheader("Hour by hour: working days vs days off")
    prof = h.groupby(["departure_hour", "is_day_off"])["trips"].sum().reset_index()
    days = h.groupby("is_day_off")["trip_date"].nunique().rename("n_days").reset_index()
    prof = prof.merge(days, on="is_day_off")
    prof["avg_trips"] = prof["trips"] / prof["n_days"]
    prof["day"] = prof["is_day_off"].map({True: "Day off", False: "Working day"})
    st.altair_chart(
        alt.Chart(prof).mark_line(point=True).encode(
            x=alt.X("departure_hour:O", title="Hour of departure"),
            y=alt.Y("avg_trips:Q", title="Average trips in that hour"),
            color=alt.Color("day:N", title=None),
        ),
        width="stretch",
    )
    st.caption("Working days show commute peaks in the morning and late afternoon; "
               "days off build to one afternoon peak.")

# ================================================================ Trip types
with tabs[4]:
    st.markdown(
        "**Question:** what are people using the bikes for? Trip length is a rough guide: "
        "short one-way hops look like errands or the last leg of a commute; long trips and "
        "round trips (back to the same station) look like leisure."
    )
    if trip_types is None or trip_types.empty:
        st.info("Trip types appear after the next export (agg_trip_types).")
    else:
        tt = trip_types.copy()
        for col in ["year", "month", "trips", "total_duration_min"]:
            tt[col] = pd.to_numeric(tt[col], errors="coerce")
        tt["is_day_off"] = as_bool(tt["is_day_off"])
        tt["is_round_trip"] = as_bool(tt["is_round_trip"])
        tt = tt[tt["year"].isin(chosen)]
        tt["day"] = tt["is_day_off"].map({True: "Day off", False: "Working day"})

        a1, a2, a3 = st.columns(3)
        total = tt["trips"].sum()
        a1.metric("Under 10 minutes", f"{100 * tt.loc[tt['duration_band'] < '3', 'trips'].sum() / total:.0f}%")
        a2.metric("Over 30 minutes", f"{100 * tt.loc[tt['duration_band'] >= '5', 'trips'].sum() / total:.0f}%")
        a3.metric("Round trips", f"{100 * tt.loc[tt['is_round_trip'] == True, 'trips'].sum() / total:.1f}%")  # noqa: E712

        def shares(col):
            g = tt.groupby(["day", col])["trips"].sum().reset_index()
            g["share"] = g["trips"] / g.groupby("day")["trips"].transform("sum")
            g["band"] = g[col].str.split(": ").str[-1]
            return g

        dur = shares("duration_band")
        st.subheader("How long are trips?")
        st.altair_chart(
            alt.Chart(dur).mark_bar().encode(
                x=alt.X("band:N", sort=list(dict.fromkeys(dur.sort_values("duration_band")["band"])),
                        title="Trip duration"),
                xOffset="day:N",
                y=alt.Y("share:Q", title="Share of trips", axis=alt.Axis(format="%")),
                color=alt.Color("day:N", title=None),
                tooltip=["day:N", "band:N", alt.Tooltip("share:Q", format=".1%"),
                         alt.Tooltip("trips:Q", format=",")],
            ),
            width="stretch",
        )
        dist = shares("distance_band")
        dist = dist[dist["distance_band"] != "0: unknown"]
        st.subheader("How far do people ride?")
        st.altair_chart(
            alt.Chart(dist).mark_bar().encode(
                x=alt.X("band:N", sort=list(dict.fromkeys(dist.sort_values("distance_band")["band"])),
                        title="Distance"),
                xOffset="day:N",
                y=alt.Y("share:Q", title="Share of trips", axis=alt.Axis(format="%")),
                color=alt.Color("day:N", title=None),
                tooltip=["day:N", "band:N", alt.Tooltip("share:Q", format=".1%")],
            ),
            width="stretch",
        )
        st.subheader("Are trips changing over the years?")
        yr = tt.groupby("year").apply(lambda g: pd.Series({
            "Short (under 10 min)": g.loc[g["duration_band"] < "3", "trips"].sum() / g["trips"].sum(),
            "Long (over 30 min)": g.loc[g["duration_band"] >= "5", "trips"].sum() / g["trips"].sum(),
            "Round trips": g.loc[g["is_round_trip"] == True, "trips"].sum() / g["trips"].sum(),  # noqa: E712
        }), include_groups=False).reset_index().melt("year", var_name="type", value_name="share")
        yr["year"] = yr["year"].astype(int).astype(str)
        st.altair_chart(
            alt.Chart(yr).mark_line(point=True).encode(
                x=alt.X("year:N", title=None),
                y=alt.Y("share:Q", title="Share of trips", axis=alt.Axis(format="%")),
                color=alt.Color("type:N", title=None),
                tooltip=["year:N", "type:N", alt.Tooltip("share:Q", format=".1%")],
            ),
            width="stretch",
        )
        st.caption("Bands use the trip's own duration and the distance reported by the bike. "
                   "From 2024 the included ride time was doubled from 30 to 60 minutes, which is "
                   "when the share of trips over 30 minutes jumps.")

# ================================================================ Stations
with tabs[5]:
    st.markdown(
        "**Question:** where do bikes pile up or run out? A station that loses bikes every day "
        "needs the operator to bring them back by van."
    )
    totals = (
        sd.groupby("station_id")[["departures", "arrivals", "net_flow"]].sum().reset_index()
        .merge(stations[["station_id", "station_name"]], on="station_id", how="left")
    )
    totals["net_per_day"] = totals["net_flow"] / max(n_days, 1)
    left, right = st.columns(2)
    left.subheader("Busiest stations")
    left.dataframe(
        totals.nlargest(15, "departures")[["station_name", "departures", "arrivals"]]
        .rename(columns={"station_name": "Station", "departures": "Departures", "arrivals": "Arrivals"}),
        hide_index=True, width="stretch",
    )
    right.subheader("Stations that run out of bikes")
    right.dataframe(
        totals.nsmallest(15, "net_flow")[["station_name", "net_flow", "net_per_day"]]
        .rename(columns={"station_name": "Station", "net_flow": "Bikes lost (total)",
                         "net_per_day": "Bikes lost per day"}),
        hide_index=True, width="stretch",
        column_config={"Bikes lost per day": st.column_config.NumberColumn(format="%.1f")},
    )
    st.subheader("Stations where bikes pile up")
    st.dataframe(
        totals.nlargest(10, "net_flow")[["station_name", "net_flow", "net_per_day"]]
        .rename(columns={"station_name": "Station", "net_flow": "Bikes gained (total)",
                         "net_per_day": "Bikes gained per day"}),
        hide_index=True, width="stretch",
        column_config={"Bikes gained per day": st.column_config.NumberColumn(format="%.1f")},
    )
    st.caption("Net flow = arrivals minus departures from riders' trips; the operator's own "
               "redistribution is not in the data.")

    st.subheader("Map: where bikes run out and pile up")
    if HAS_GEO:
        geo = totals.merge(stations[["station_id", "lat", "lon", "city"]], on="station_id", how="left")
        geo = geo.dropna(subset=["lat", "lon"]).copy()
        lim = max(geo["net_per_day"].abs().quantile(0.95), 1)
        geo["color"] = geo["net_per_day"].map(
            lambda v: "#d6404e" if v <= -lim / 4 else ("#2b7bd6" if v >= lim / 4 else "#9a9a9a"))
        geo["size"] = 20 + 160 * (geo["departures"] / geo["departures"].max()) ** 0.5
        st.map(geo, latitude="lat", longitude="lon", color="color", size="size")
        st.caption("Red: loses bikes; blue: gains bikes; grey: roughly balanced. "
                   f"Dot size shows departures. {len(geo):,} stations with known coordinates. "
                   "Locations come from HSL's 2021 station list, so a few stations that later moved "
                   "are shown at their old spot.")
    else:
        st.info("The map appears once the station coordinates seed is loaded.")

# ================================================================ Routes
with tabs[6]:
    st.markdown(
        "**Question:** which trips do people actually make? Each route is a station-to-station "
        "pair; routes with fewer than 10 trips in a year are not published."
    )
    if od_pairs is None or od_pairs.empty:
        st.info("Routes appear after the next export (agg_od_pairs).")
    else:
        od = od_pairs.copy()
        for col in ["year", "trips", "avg_duration_min", "avg_distance_km"]:
            od[col] = pd.to_numeric(od[col], errors="coerce")
        od = od[od["year"].isin(chosen)]
        names = stations.set_index("station_id")["station_name"]
        routes = (od.groupby(["departure_station_id", "return_station_id"])
                  .agg(trips=("trips", "sum"), minutes=("avg_duration_min", "mean"),
                       km=("avg_distance_km", "mean")).reset_index())
        routes["From"] = routes["departure_station_id"].map(names)
        routes["To"] = routes["return_station_id"].map(names)
        one_way = routes[routes["departure_station_id"] != routes["return_station_id"]]
        st.subheader("Most popular routes")
        st.dataframe(
            one_way.nlargest(20, "trips")[["From", "To", "trips", "minutes", "km"]]
            .rename(columns={"trips": "Trips", "minutes": "Avg minutes", "km": "Avg km"}),
            hide_index=True, width="stretch",
            column_config={"Avg minutes": st.column_config.NumberColumn(format="%.1f"),
                           "Avg km": st.column_config.NumberColumn(format="%.2f")},
        )
        st.subheader("Where do people go from a station?")
        options = (routes.groupby("From")["trips"].sum().sort_values(ascending=False).index.tolist())
        if options:
            pick = st.selectbox("Station", options)
            dest = routes[routes["From"] == pick].nlargest(10, "trips")
            st.altair_chart(
                alt.Chart(dest).mark_bar().encode(
                    x=alt.X("trips:Q", title="Trips"),
                    y=alt.Y("To:N", sort="-x", title=None),
                    tooltip=["To:N", "trips:Q", alt.Tooltip("minutes:Q", format=".1f")],
                ),
                width="stretch",
            )
            st.caption("Top 10 destinations. A bar with the same name is a round trip.")

# ================================================================ Helsinki vs Espoo
with tabs[7]:
    st.markdown(
        "**Question:** do the two cities use the bikes differently? Helsinki is dense; Espoo is "
        "more suburban, with longer distances between stations."
    )
    if not HAS_GEO:
        st.info("This comparison appears once the station city seed is loaded.")
    else:
        city_of = stations.set_index("station_id")["city"]
        sc = sd.assign(city=sd["station_id"].map(city_of))
        sc = sc[sc["city"].isin(["Helsinki", "Espoo"])]
        per = (sc.groupby(["city", "trip_date"])["departures"].sum().reset_index()
               .merge(d[["trip_date", "year", "is_day_off", "is_rainy_day", "temp_mean_c"]],
                      on="trip_date", how="left"))
        n_st = sc[sc["departures"] > 0].groupby("city")["station_id"].nunique()
        summary_c = per.groupby("city").agg(trips=("departures", "sum"),
                                            per_day=("departures", "mean")).reset_index()
        summary_c["stations"] = summary_c["city"].map(n_st)
        summary_c["per_station_day"] = summary_c["per_day"] / summary_c["stations"]
        summary_c["share"] = summary_c["trips"] / summary_c["trips"].sum()
        rain_c = {}
        for c, g in per[per["is_day_off"] == False].dropna(subset=["is_rainy_day"]).groupby("city"):  # noqa: E712
            rain_c[c] = pct(g.loc[g["is_rainy_day"] == True, "departures"].mean(),   # noqa: E712
                            g.loc[g["is_rainy_day"] == False, "departures"].mean())  # noqa: E712
        dayoff_c = {c: pct(g.loc[g["is_day_off"] == True, "departures"].mean(),   # noqa: E712
                           g.loc[g["is_day_off"] == False, "departures"].mean())  # noqa: E712
                    for c, g in per.groupby("city")}
        summary_c["rain"] = summary_c["city"].map(rain_c)
        summary_c["dayoff"] = summary_c["city"].map(dayoff_c)
        st.dataframe(
            summary_c.rename(columns={
                "city": "City", "trips": "Trips started", "share": "Share",
                "stations": "Stations used", "per_day": "Trips/day",
                "per_station_day": "Trips per station per day",
                "rain": "Rainy working day", "dayoff": "Day off vs working day"}),
            hide_index=True, width="stretch",
            column_config={
                "Trips started": st.column_config.NumberColumn(format="%d"),
                "Share": st.column_config.NumberColumn(format="percent"),
                "Trips/day": st.column_config.NumberColumn(format="%d"),
                "Trips per station per day": st.column_config.NumberColumn(format="%.1f"),
                "Rainy working day": st.column_config.NumberColumn(format="%+.0f%%"),
                "Day off vs working day": st.column_config.NumberColumn(format="%+.0f%%"),
            },
        )
        st.caption("Trips are counted in the city where they start. Percentages compare average "
                   "trips per day.")

        st.subheader("Each season by city")
        mc = per.assign(month=per["trip_date"].dt.month, year=per["trip_date"].dt.year)
        mc = mc.groupby(["city", "year"])["departures"].mean().reset_index()
        mc["year"] = mc["year"].astype(str)
        st.altair_chart(
            alt.Chart(mc).mark_bar().encode(
                x=alt.X("year:N", title=None),
                xOffset="city:N",
                y=alt.Y("departures:Q", title="Average trips per day"),
                color=alt.Color("city:N", title=None),
                tooltip=["city:N", "year:N", alt.Tooltip("departures:Q", format=",.0f")],
            ),
            width="stretch",
        )

        if city_flows is not None and not city_flows.empty:
            cf = city_flows.copy()
            cf["year"] = pd.to_numeric(cf["year"], errors="coerce")
            cf["trips"] = pd.to_numeric(cf["trips"], errors="coerce")
            cf = cf[cf["year"].isin(chosen)]
            cf = cf[cf["departure_city"].isin(["Helsinki", "Espoo"]) & cf["return_city"].isin(["Helsinki", "Espoo"])]
            flows = cf.groupby(["departure_city", "return_city"])["trips"].sum().reset_index()
            flows["share"] = flows["trips"] / flows["trips"].sum()
            st.subheader("Trips between the cities")
            st.dataframe(flows.rename(columns={"departure_city": "From", "return_city": "To",
                                               "trips": "Trips", "share": "Share"}),
                         hide_index=True, width="stretch",
                         column_config={"Share": st.column_config.NumberColumn(format="percent")})

# ================================================================ Estimate a day
with tabs[8]:
    st.markdown(
        "**Question:** how many trips should we expect tomorrow? A simple linear model fitted "
        "on the selected years: temperature, rain, day off and whether it is April or October."
    )
    fit = d.dropna(subset=["temp_mean_c", "precipitation_mm", "is_day_off"])
    if len(fit) >= 10:
        def features(temp, rain, off, shoulder):
            return np.column_stack([np.ones(len(temp)), temp, np.log1p(rain), off, shoulder])

        X = features(fit["temp_mean_c"].to_numpy(), fit["precipitation_mm"].clip(lower=0).to_numpy(),
                     fit["is_day_off"].astype(float).to_numpy(),
                     fit["month"].isin([4, 10]).astype(float).to_numpy())
        y = fit["trips"].to_numpy()
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
        mae = np.abs(resid).mean()

        a, b = st.columns(2)
        temp_in = a.slider("Mean temperature (°C)", -5.0, 30.0, 16.0, 0.5)
        rain_in = a.slider("Rain (mm)", 0.0, 30.0, 0.0, 0.5)
        off_in = b.radio("Day type", ["Working day", "Weekend or holiday"], horizontal=True)
        month_in = b.selectbox("Month", list(MONTHS.values()), index=2)
        row = features(np.array([temp_in]), np.array([rain_in]),
                       np.array([1.0 if off_in != "Working day" else 0.0]),
                       np.array([1.0 if month_in in ("Apr", "Oct") else 0.0]))[0]
        est = float(row @ coef)
        st.metric("Expected trips", f"{max(est, 0):,.0f}",
                  f"typical error ± {mae:,.0f}", delta_color="off")
        st.caption(
            f"The model explains {100 * r2:.0f}% of day-to-day variation (R²) on "
            f"{len(fit):,} days. It is a planning aid, not a forecast service: it ignores events, "
            "wind, station closures and long-term trends."
        )
    else:
        st.info("Not enough days with weather data in the selected years.")

# ================================================================ Data quality
with tabs[9]:
    st.markdown(
        "**Question:** can the numbers be trusted? Every raw row is labelled, nothing is "
        "dropped silently, and yearly totals are checked against the city's published figures."
    )
    summary = quality.groupby("quality_status")["row_count"].sum().sort_values(ascending=False)
    st.dataframe(summary.rename("Rows").reset_index().rename(columns={"quality_status": "Label"}),
                 hide_index=True)
    st.markdown(
        "- **April to July 2021** files list every trip twice; duplicates are removed.\n"
        "- **October 2021** has no trip durations; they are calculated from the timestamps.\n"
        "- **2025** uses a station code `*40` that is not a number; those trips are flagged, not guessed."
    )
    st.subheader("Rows per load file and why rows were rejected")
    st.dataframe(quality.sort_values(["source_file", "quality_status"]),
                 hide_index=True, width="stretch")
