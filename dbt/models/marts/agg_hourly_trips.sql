-- Trips per date and departure hour (0-23), for daily profiles on work days vs days off.

select
    t.trip_date,
    t.departure_hour,
    c.is_day_off,
    c.is_rainy_day,
    count(*) as trips
from {{ ref('fct_trips') }} t
left join {{ ref('dim_date') }} c on c.date_day = t.trip_date
group by t.trip_date, t.departure_hour, c.is_day_off, c.is_rainy_day
