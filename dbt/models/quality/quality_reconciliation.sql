-- Our yearly totals next to published totals. A large gap means a load or
-- cleaning problem (or a scope difference, see the seed's scope column).

with ours as (

    select
        extract(year from departed_at)                              as year,
        count(*)                                                    as rows_after_dedup,
        sum(case when quality_status = 'valid' then 1 else 0 end)   as valid_trips
    from {{ ref('stg_trips') }}
    where departed_at is not null
    group by 1

)

select
    o.year,
    o.rows_after_dedup,
    o.valid_trips,
    t.official_trips,
    round(100.0 * o.valid_trips / nullif(t.official_trips, 0), 1)  as valid_as_pct_of_official,
    t.scope,
    t.source
from ours o
left join {{ ref('official_trip_totals') }} t on t.year = o.year
