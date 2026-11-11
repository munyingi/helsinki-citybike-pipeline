-- Singular test: no valid trip may end before it starts.
select trip_id, departed_at, returned_at
from {{ ref('fct_trips') }}
where returned_at < departed_at
