-- One row per piece sold.
select
    s.sale_id,
    s.inventory_id,
    s.buyer_customer_id as customer_id,
    s.sale_location_id as location_id,
    p.stock_pool_location_id,
    s.sale_date,
    s.payment_type,
    s.delivery_type,
    s.net_sales_amount,
    p.acquisition_cost as cost_of_goods_sold,
    (s.net_sales_amount - p.acquisition_cost)::decimal(18, 2) as gross_margin_amount,
    p.days_on_hand as days_to_sell,
    ld.is_comp as is_comp_day
from {{ ref('stg_sales') }} as s
inner join {{ ref('int_pieces') }} as p
    on s.inventory_id = p.inventory_id
left join {{ ref('int_location_days') }} as ld
    on s.sale_location_id = ld.location_id
   and s.sale_date = ld.calendar_date
