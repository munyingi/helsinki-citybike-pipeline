-- One row per raw trip, typed, with a quality flag. Nothing is dropped here:
-- invalid rows are kept and labelled so they can be counted in quality/.

with source as (

    select * from {{ source('raw', 'trips') }}

),

typed as (

    select
        try_cast(departure as timestamp)            as departed_at,     -- local Helsinki time
        try_cast(return_time as timestamp)          as returned_at,
        try_cast(departure_station_id as integer)   as departure_station_id,
        trim(departure_station_name)                as departure_station_name,
        try_cast(return_station_id as integer)      as return_station_id,
        trim(return_station_name)                   as return_station_name,
        try_cast(covered_distance_m as double)      as distance_m,
        try_cast(duration_sec as double)            as duration_s,
        source_file,
        loaded_at
    from source

),

deduplicated as (

    -- Exact duplicate rows (same everything) are kept once.
    select *
    from typed
    qualify row_number() over (
        partition by departed_at, returned_at, departure_station_id, return_station_id,
                     distance_m, duration_s
        order by loaded_at
    ) = 1

)

select
    md5(
        coalesce(cast(departed_at as varchar), '') || '|' ||
        coalesce(cast(returned_at as varchar), '') || '|' ||
        coalesce(cast(departure_station_id as varchar), '') || '|' ||
        coalesce(cast(return_station_id as varchar), '') || '|' ||
        coalesce(cast(distance_m as varchar), '') || '|' ||
        coalesce(cast(duration_s as varchar), '')
    )                                                            as trip_id,
    *,
    case
        when departed_at is null or returned_at is null
          or departure_station_id is null or return_station_id is null
          or duration_s is null                                  then 'missing_field'
        when returned_at < departed_at                           then 'returned_before_departure'
        when duration_s < {{ var('min_trip_seconds') }}          then 'too_short_time'
        when distance_m is not null
         and distance_m < {{ var('min_trip_metres') }}           then 'too_short_distance'
        when duration_s > {{ var('max_trip_seconds') }}          then 'too_long'
        else 'valid'
    end                                                          as quality_status
from deduplicated
