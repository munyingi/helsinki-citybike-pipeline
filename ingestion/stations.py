"""Turn HSL's station list into a small dbt seed (dbt/seeds/stations.csv).

Source: "Helsingin ja Espoon kaupunkipyoraasemat avoin" (HSL open data, CC BY 4.0),
downloaded as CSV from public-transport-hslhrt.opendata.arcgis.com and saved as
data/raw/stations.csv.

In the source, Espoo stations have Kaupunki = "Espoo" and Helsinki stations leave it
blank, so a blank city is read as Helsinki.

Usage:
    python ingestion/stations.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "stations.csv"
OUT = ROOT / "dbt" / "seeds" / "stations.csv"


def main() -> None:
    rows = []
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            city = (r.get("Kaupunki") or "").strip() or "Helsinki"
            rows.append({
                "station_id": int(r["ID"]),
                "station_name_official": r["Nimi"].strip(),
                "city": city,
                "capacity": int(float(r["Kapasiteet"])) if r.get("Kapasiteet") else "",
                "lat": round(float(r["y"]), 6),
                "lon": round(float(r["x"]), 6),
            })
    rows.sort(key=lambda r: r["station_id"])
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    cities = {}
    for r in rows:
        cities[r["city"]] = cities.get(r["city"], 0) + 1
    print(f"{len(rows)} stations -> {OUT.relative_to(ROOT)}  {cities}")


if __name__ == "__main__":
    main()
