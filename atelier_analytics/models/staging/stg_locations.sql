select
    location_id,
    location_name,
    city,
    state_province,
    country,
    open_date,
    close_date,
    case when location_id = 'LOC-ONL' then 'Online' else 'Store' end as channel,
    -- Online orders ship from New York stock, so its inventory sits in the NYC pool.
    case when location_id = 'LOC-ONL' then 'LOC-NYC' else location_id end as stock_pool_location_id
from {{ source('raw', 'locations') }}
