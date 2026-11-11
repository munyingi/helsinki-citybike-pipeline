-- One row per station id seen in the trip data.
-- Name = the most recently used name (stations are sometimes renamed).
-- Coordinates and city come later from HSL's station file (see README "Next steps").

with station_events as (

    select departure_station_id as station_id, departure_station_name as station_name, departed_at as seen_at
    from {{ ref('stg_trips') }}
    where quality_status = 'valid'

    union all

    select return_station_id, return_station_name, returned_at
    from {{ ref('stg_trips') }}
    where quality_status = 'valid'

)

select
    station_id,
    max_by(station_name, seen_at)   as station_name,
    min(seen_at)                    as first_seen_at,
    max(seen_at)                    as last_seen_at,
    count(*)                        as trip_events
from station_events
where station_id is not null
group by station_id
