-- One row per piece acquired: the buy-in, its attributes, when it reached the floor, and its sale if it has sold.
with floor_dates as (
    select
        inventory_id,
        min(snapshot_date) as floor_date,
        max(snapshot_date) as last_on_hand_date
    from {{ ref('stg_inventory_snapshot') }}
    group by 1
)

select
    p.inventory_id,
    p.purchase_id,
    p.consignor_customer_id,
    p.purchase_location_id,
    loc.stock_pool_location_id,
    p.purchase_date,
    p.acquisition_cost,
    p.pipeline_stage,
    p.is_stocked,
    f.floor_date,
    -- Pieces bought before history starts arrive in the first snapshot as opening stock, not as receipts.
    p.purchase_date < date '{{ var("history_start_date") }}' as is_opening_stock,
    s.sale_id,
    s.sale_date,
    s.sale_location_id,
    s.net_sales_amount,
    s.sale_id is not null as is_sold,
    datediff('day', f.floor_date, coalesce(s.sale_date, date '{{ var("as_of_date") }}')) as days_on_hand
from {{ ref('stg_purchasing') }} as p
left join {{ ref('stg_locations') }} as loc
    on p.purchase_location_id = loc.location_id
left join floor_dates as f
    on p.inventory_id = f.inventory_id
left join {{ ref('stg_sales') }} as s
    on p.inventory_id = s.inventory_id
