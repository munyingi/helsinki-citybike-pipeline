"""Create small SYNTHETIC sample files for CI and offline testing.

The files mimic the real source formats (HSL trip CSV headers, FMI 'simple'
WFS XML) so CI exercises the same parsing code as a real load. The numbers
are random and must never be used for analysis.

Usage:
    python scripts/make_fixtures.py
"""
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
random.seed(42)


def make_trips(n: int = 3000) -> None:
    stations = [(f"{i:03d}", f"Sample station {i}") for i in range(1, 41)]
    rows = []
    start = datetime(2025, 5, 1, 6, 0, 0)
    for _ in range(n):
        dep_id, dep_name = random.choice(stations)
        ret_id, ret_name = random.choice(stations)
        departure = start + timedelta(days=random.randint(0, 13), minutes=random.randint(0, 17 * 60))
        duration = random.randint(120, 2400)
        rows.append({
            "Departure": departure.strftime("%Y-%m-%dT%H:%M:%S"),
            "Return": (departure + timedelta(seconds=duration)).strftime("%Y-%m-%dT%H:%M:%S"),
            "Departure station id": dep_id,
            "Departure station name": dep_name,
            "Return station id": ret_id,
            "Return station name": ret_name,
            "Covered distance (m)": str(round(duration * random.uniform(2.0, 4.5), 1)),
            "Duration (sec.)": str(duration),
        })
    # Deliberately bad rows so the data-quality layer has something to catch.
    bad = dict(rows[0])
    rows.append({**bad, "Duration (sec.)": "4"})                      # too short
    rows.append({**bad, "Duration (sec.)": "90000"})                  # too long
    rows.append({**bad, "Return station id": ""})                     # missing field
    rows.append({**bad, "Return": "2025-04-30T06:00:00"})             # returns before departure
    rows.append(dict(rows[1]))                                        # exact duplicate
    FIXTURES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(FIXTURES / "2025-05.csv", index=False)
    print(f"trips fixture: {len(rows)} rows")


def make_weather() -> None:
    members = []
    day = date(2025, 5, 1)
    while day <= date(2025, 5, 14):
        values = {
            "rrday": random.choice(["-1.0", "0.0", "0.4", "3.2", "11.5"]),
            "tday": f"{random.uniform(5, 18):.1f}",
            "tmin": f"{random.uniform(0, 8):.1f}",
            "tmax": f"{random.uniform(12, 24):.1f}",
            "snow": "-1.0",
        }
        for name, value in values.items():
            members.append(
                "<wfs:member><BsWfs:BsWfsElement gml:id=\"x\">"
                "<BsWfs:Location><gml:Point><gml:pos>60.17523 24.94459</gml:pos></gml:Point></BsWfs:Location>"
                f"<BsWfs:Time>{day.isoformat()}T00:00:00Z</BsWfs:Time>"
                f"<BsWfs:ParameterName>{name}</BsWfs:ParameterName>"
                f"<BsWfs:ParameterValue>{value}</BsWfs:ParameterValue>"
                "</BsWfs:BsWfsElement></wfs:member>"
            )
        day += timedelta(days=1)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">'
        + "".join(members)
        + "</wfs:FeatureCollection>"
    )
    (FIXTURES / "fmi_sample.xml").write_text(xml, encoding="utf-8")
    print(f"weather fixture: {len(members)} observations")


if __name__ == "__main__":
    make_trips()
    make_weather()
