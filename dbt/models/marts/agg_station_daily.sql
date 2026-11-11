-- Departures and arrivals per station per day.
-- net_flow > 0: bikes pile up at the station; < 0: the station drains.

with departures as (

    select trip_date, departure_station_id as station_id, count(*) as departures
    from {{ ref('fct_trips') }}
    group by 1, 2

),

arrivals as (

    select cast(returned_at as date) as trip_date, return_station_id as station_id, count(*) as arrivals
    from {{ ref('fct_trips') }}
    group by 1, 2

)

select
    coalesce(d.trip_date, a.trip_date)          as trip_date,
    coalesce(d.station_id, a.station_id)        as station_id,
    coalesce(d.departures, 0)                   as departures,
    coalesce(a.arrivals, 0)                     as arrivals,
    coalesce(a.arrivals, 0) - coalesce(d.departures, 0) as net_flow
from departures d
full outer join arrivals a
    on a.trip_date = d.trip_date
   and a.station_id = d.station_id
