select
    location_id,
    location_name,
    channel,
    city,
    state_province,
    country,
    stock_pool_location_id,
    open_date,
    close_date,
    (case
        when day(open_date) = 1 then open_date
        else (date_trunc('month', open_date) + interval 1 month)::date
    end + to_months({{ var('comp_months_open') }}))::date as comp_start_date
from {{ ref('stg_locations') }}
