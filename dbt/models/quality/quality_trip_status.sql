-- How many rows each load file produced, and why rows were rejected.
-- Feeds the "Data quality" page of the dashboard.

with raw_counts as (

    select source_file, count(*) as raw_rows
    from {{ source('raw', 'trips') }}
    group by source_file

),

status_counts as (

    select source_file, quality_status, count(*) as row_count
    from {{ ref('stg_trips') }}
    group by source_file, quality_status

),

duplicates as (

    select r.source_file, 'duplicate_removed' as quality_status,
           r.raw_rows - coalesce(sum(s.row_count), 0) as row_count
    from raw_counts r
    left join status_counts s on s.source_file = r.source_file
    group by r.source_file, r.raw_rows

),

all_statuses as (

    select * from status_counts
    union all
    select * from duplicates

)

select
    a.source_file,
    r.raw_rows,
    a.quality_status,
    a.row_count,
    round(100.0 * a.row_count / nullif(r.raw_rows, 0), 3) as pct_of_raw
from all_statuses a
join raw_counts r on r.source_file = a.source_file
