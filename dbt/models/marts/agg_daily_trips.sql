-- One row per day with trips, joined to weather and calendar. Main table for analysis.

with daily as (

    select
        trip_date,
        count(*)                        as trips,
        avg(duration_min)               as avg_duration_min,
        median(duration_min)            as median_duration_min,
        avg(distance_m) / 1000.0        as avg_distance_km,
        sum(distance_m) / 1000.0        as total_distance_km,
        count(distinct departure_station_id) as active_stations
    from {{ ref('fct_trips') }}
    group by trip_date

)

select
    d.trip_date,
    d.trips,
    d.avg_duration_min,
    d.median_duration_min,
    d.avg_distance_km,
    d.total_distance_km,
    d.active_stations,
    c.year,
    c.month,
    c.iso_weekday,
    c.weekday_name,
    c.is_weekend,
    c.is_public_holiday,
    c.holiday_name,
    c.special_day_name,
    c.is_day_off,
    c.precipitation_mm,
    c.temp_mean_c,
    c.temp_max_c,
    c.is_rainy_day,
    c.temp_band
from daily d
left join {{ ref('dim_date') }} c on c.date_day = d.trip_date
