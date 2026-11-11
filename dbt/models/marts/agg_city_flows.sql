-- Trips between Helsinki and Espoo per year, by the city of the start and end station.
-- Uses every valid trip, so it is exact even for small flows.

select
    extract(year from t.trip_date)      as year,
    ds.city                             as departure_city,
    rs.city                             as return_city,
    count(*)                            as trips,
    avg(t.duration_min)                 as avg_duration_min,
    avg(t.distance_m) / 1000.0          as avg_distance_km
from {{ ref('fct_trips') }} t
join {{ ref('dim_station') }} ds on ds.station_id = t.departure_station_id
join {{ ref('dim_station') }} rs on rs.station_id = t.return_station_id
group by 1, 2, 3
