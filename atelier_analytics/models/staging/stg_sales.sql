select
    sale_id,
    inventory_id,
    customer_id as buyer_customer_id,
    location_id as sale_location_id,
    sale_date,
    sales_price::decimal(18, 2) as net_sales_amount,
    payment_type,
    delivery_type
from {{ source('raw', 'sales') }}
