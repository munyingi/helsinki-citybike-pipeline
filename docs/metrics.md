# Metric definitions

Every number in the dashboard, README and articles uses these definitions.
Thresholds live in `dbt/dbt_project.yml` (`vars`) so they are defined once.

| Term | Definition |
|---|---|
| Trip | One row in HSL's Origin-Destination file (Helsinki + Espoo), after removing exact duplicates. |
| Valid trip | A trip with departure and return times, both station ids and a duration; that does not end before it starts; lasts at least 10 seconds and at most 5 hours; and, when distance is reported, covers at least 10 metres. |
| Rejected trip | Any trip that is not valid. Counted by reason in `quality.quality_trip_status`. |
| Trip date | Date of departure, local Helsinki time. |
| Rainy day | Daily precipitation at FMI Helsinki Kaisaniemi of 1 mm or more. FMI's value -1 means no rain at all and is stored as 0. |
| Temperature | Daily mean temperature at Kaisaniemi (FMI `tday`). |
| Day off | Saturday, Sunday or a Finnish public holiday (from the `holidays` package, including Midsummer Eve and Christmas Eve). |
| Net flow | Arrivals minus departures at a station on a day. Negative = the station drains. |

## Known limitations

- City bikes run only in season (roughly April to October), so there is no winter data.
- Trips show realised use, not demand: when a station is empty, demand there is invisible.
- One weather station represents the whole Helsinki-Espoo area.
- Results are associations, not proof of cause.
- The published official totals used in `quality_reconciliation` may cover a different scope (Helsinki only) than the OD data (Helsinki + Espoo).
