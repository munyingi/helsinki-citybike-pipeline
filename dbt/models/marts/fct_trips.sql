-- Valid trips only. Grain: one row per trip.

select
    trip_id,
    departed_at,
    returned_at,
    cast(departed_at as date)                       as trip_date,
    extract(hour from departed_at)                  as departure_hour,
    departure_station_id,
    return_station_id,
    departure_station_id = return_station_id        as is_round_trip,
    distance_m,
    duration_s,
    duration_s / 60.0                               as duration_min,
    source_file
from {{ ref('stg_trips') }}
where quality_status = 'valid'
