-- Station-to-station routes per year. Pairs with fewer than 10 trips in a year are
-- left out, which keeps the export small and avoids publishing rare, identifiable trips.

select
    extract(year from trip_date)        as year,
    departure_station_id,
    return_station_id,
    count(*)                            as trips,
    avg(duration_min)                   as avg_duration_min,
    avg(distance_m) / 1000.0            as avg_distance_km
from {{ ref('fct_trips') }}
group by 1, 2, 3
having count(*) >= 10
