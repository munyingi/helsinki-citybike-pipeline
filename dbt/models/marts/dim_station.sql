-- One row per station id seen in the trip data.
-- Name = the most recently used name (stations are sometimes renamed).
-- City, capacity and coordinates come from HSL's station list (seed: stations).
-- That list dates from 2021, so a few stations that later moved keep their old
-- location. Ids missing from it get a city from HSL's numbering: 501-899 are Espoo.

with station_events as (

    select departure_station_id as station_id, departure_station_name as station_name, departed_at as seen_at
    from {{ ref('stg_trips') }}
    where quality_status = 'valid'

    union all

    select return_station_id, return_station_name, returned_at
    from {{ ref('stg_trips') }}
    where quality_status = 'valid'

),

stations_seen as (

    select
        station_id,
        max_by(station_name, seen_at)   as station_name,
        min(seen_at)                    as first_seen_at,
        max(seen_at)                    as last_seen_at,
        count(*)                        as trip_events
    from station_events
    where station_id is not null
    group by station_id

)

select
    s.station_id,
    s.station_name,
    coalesce(
        r.city,
        case
            when s.station_id between 501 and 899 then 'Espoo'
            when s.station_id >= 900 then 'Other'
            else 'Helsinki'
        end
    )                                   as city,
    r.capacity,
    r.lat,
    r.lon,
    r.station_id is not null            as is_in_station_list,
    s.first_seen_at,
    s.last_seen_at,
    s.trip_events
from stations_seen s
left join {{ ref('stations') }} r on r.station_id = s.station_id
