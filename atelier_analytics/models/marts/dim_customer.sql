-- Non-PII customer attributes only. See stg_customers.
with buys as (
    select buyer_customer_id as customer_id, min(sale_date) as first_purchase_date, count(*) as lifetime_purchases
    from {{ ref('stg_sales') }}
    group by 1
),

consigns as (
    select consignor_customer_id as customer_id, count(*) as lifetime_consignments
    from {{ ref('stg_purchasing') }}
    group by 1
)

select
    c.customer_id,
    c.profile_create_date,
    c.customer_city,
    c.state_province,
    c.country,
    c.country_code,
    c.is_domestic,
    b.first_purchase_date,
    coalesce(b.lifetime_purchases, 0)::integer as lifetime_purchases,
    coalesce(k.lifetime_consignments, 0)::integer as lifetime_consignments,
    case
        when coalesce(b.lifetime_purchases, 0) > 0 and coalesce(k.lifetime_consignments, 0) > 0 then 'Buyer and consignor'
        when coalesce(b.lifetime_purchases, 0) > 0 then 'Buyer'
        when coalesce(k.lifetime_consignments, 0) > 0 then 'Consignor'
        else 'Prospect'
    end as customer_role
from {{ ref('stg_customers') }} as c
left join buys as b on c.customer_id = b.customer_id
left join consigns as k on c.customer_id = k.customer_id
