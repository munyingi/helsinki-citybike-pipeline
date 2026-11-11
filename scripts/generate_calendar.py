"""Generate dbt/seeds/calendar.csv: one row per day with Finnish public holidays.

Holidays come from the `holidays` package (Finland, English names), which
includes Midsummer Eve and Christmas Eve as days off.

Usage:
    python scripts/generate_calendar.py            # 2021-2026
    python scripts/generate_calendar.py 2016 2027  # custom range
"""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import holidays

OUT = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "calendar.csv"


def main(first_year: int = 2021, last_year: int = 2026) -> None:
    fi = holidays.Finland(years=range(first_year, last_year + 1), language="en_US")
    day = date(first_year, 1, 1)
    end = date(last_year, 12, 31)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date_day", "year", "month", "day_of_month", "iso_weekday",
                         "weekday_name", "is_weekend", "is_public_holiday", "holiday_name"])
        while day <= end:
            name = fi.get(day)
            writer.writerow([
                day.isoformat(), day.year, day.month, day.day, day.isoweekday(),
                day.strftime("%A"), day.isoweekday() >= 6, name is not None, name or "",
            ])
            day += timedelta(days=1)
    print(f"Wrote {OUT} ({first_year}-{last_year})")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:3]]
    main(*args)
