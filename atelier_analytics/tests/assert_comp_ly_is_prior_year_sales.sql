-- The LY column must equal what the same location actually sold on the LY date.
with actual as (
    select location_id, sale_date, sum(net_sales_amount) as amount
    from {{ ref('fct_sales') }}
    group by 1, 2
)

select c.location_id, c.sale_date, c.ly_date, c.ly_net_sales_amount, a.amount
from {{ ref('fct_comp_sales_daily') }} as c
left join actual as a
    on c.location_id = a.location_id and c.ly_date = a.sale_date
where c.ly_net_sales_amount <> coalesce(a.amount, 0)
