-- Long FMI rows -> one row per date. If a date was loaded twice, the latest load wins.

with source as (

    select
        try_cast(obs_date as date)      as weather_date,
        parameter,
        try_cast(nullif(lower(trim(value)), 'nan') as double) as value,
        loaded_at
    from {{ source('raw', 'weather_daily') }}

),

latest as (

    select *
    from source
    qualify row_number() over (partition by weather_date, parameter order by loaded_at desc) = 1

)

select
    weather_date,
    -- FMI: -1 means "no rain at all"; NaN/empty means not measured (stays null).
    max(case when parameter = 'rrday' then case when value < 0 then 0 else value end end) as precipitation_mm,
    max(case when parameter = 'tday'  then value end)                                    as temp_mean_c,
    max(case when parameter = 'tmin'  then value end)                                    as temp_min_c,
    max(case when parameter = 'tmax'  then value end)                                    as temp_max_c,
    max(case when parameter = 'snow'  then case when value < 0 then 0 else value end end) as snow_depth_cm
from latest
where weather_date is not null
group by weather_date
