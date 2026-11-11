-- One row per day: calendar, holidays, special days and weather.

with calendar as (

    select * from {{ ref('calendar') }}

),

special as (

    select * from {{ ref('special_days') }}

),

weather as (

    select * from {{ ref('stg_weather_daily') }}

)

select
    c.date_day,
    c.year,
    c.month,
    c.day_of_month,
    c.iso_weekday,
    c.weekday_name,
    c.is_weekend,
    c.is_public_holiday,
    nullif(c.holiday_name, '')                                       as holiday_name,
    s.special_day_name,
    s.special_day_type,
    (c.is_weekend or c.is_public_holiday)                            as is_day_off,
    c.month between 4 and 10                                         as is_bike_season_month,
    w.precipitation_mm,
    w.temp_mean_c,
    w.temp_min_c,
    w.temp_max_c,
    w.snow_depth_cm,
    case
        when w.precipitation_mm is null then null
        else w.precipitation_mm >= {{ var('rainy_day_mm') }}
    end                                                              as is_rainy_day,
    case
        when w.temp_mean_c is null then null
        when w.temp_mean_c < 5  then '1: below 5 C'
        when w.temp_mean_c < 10 then '2: 5-10 C'
        when w.temp_mean_c < 15 then '3: 10-15 C'
        when w.temp_mean_c < 20 then '4: 15-20 C'
        else '5: 20 C and above'
    end                                                              as temp_band
from calendar c
left join special s on s.date_day = c.date_day
left join weather w on w.weather_date = c.date_day
