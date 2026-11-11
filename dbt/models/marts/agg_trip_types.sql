-- Trips by length, duration and whether they end where they started.
-- A rough proxy for trip purpose: short one-way hops vs long or round trips.
-- Grain: year, month, day off or not, duration band, distance band, round trip or not.

with trips as (

    select
        t.trip_date,
        t.duration_min,
        t.distance_m,
        t.is_round_trip,
        d.is_day_off
    from {{ ref('fct_trips') }} t
    left join {{ ref('dim_date') }} d on d.date_day = t.trip_date

)

select
    extract(year from trip_date)                    as year,
    extract(month from trip_date)                   as month,
    coalesce(is_day_off, false)                     as is_day_off,
    case
        when duration_min < 5  then '1: under 5 min'
        when duration_min < 10 then '2: 5-10 min'
        when duration_min < 20 then '3: 10-20 min'
        when duration_min < 30 then '4: 20-30 min'
        when duration_min < 60 then '5: 30-60 min'
        else '6: 60 min and over'
    end                                             as duration_band,
    case
        when distance_m is null then '0: unknown'
        when distance_m < 1000 then '1: under 1 km'
        when distance_m < 2000 then '2: 1-2 km'
        when distance_m < 3000 then '3: 2-3 km'
        when distance_m < 5000 then '4: 3-5 km'
        else '5: 5 km and over'
    end                                             as distance_band,
    is_round_trip,
    count(*)                                        as trips,
    sum(duration_min)                               as total_duration_min
from trips
group by 1, 2, 3, 4, 5, 6
