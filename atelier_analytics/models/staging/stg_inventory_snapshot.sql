select
    snapshot_date,
    inventory_id,
    purchase_id,
    sale_id,
    location_id as stock_location_id,
    sale_id is not null as is_sold_today
from {{ source('raw', 'inventory') }}
