select
    purchase_id,
    inventory_id,
    customer_id as consignor_customer_id,
    location_id as purchase_location_id,
    purchase_date,
    purchase_price::decimal(18, 2) as acquisition_cost,
    stage as pipeline_stage,
    stage = 'Available to Stock' as is_stocked
from {{ source('raw', 'purchasing') }}
