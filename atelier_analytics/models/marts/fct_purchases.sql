-- One row per buy-in.
select
    purchase_id,
    inventory_id,
    consignor_customer_id as customer_id,
    purchase_location_id as location_id,
    purchase_date,
    acquisition_cost,
    pipeline_stage,
    is_stocked,
    floor_date,
    datediff('day', purchase_date, floor_date) as days_purchase_to_floor
from {{ ref('int_pieces') }}
