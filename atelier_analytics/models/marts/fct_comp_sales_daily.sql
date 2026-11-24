-- One row per selling location per day, with this year's sales next to the same calendar date last year.
-- Comp growth is sum(ty) / sum(ly) - 1 over rows where is_comp is true. Both years use the same
-- store set because the comp flag belongs to this year's row.
with daily as (
    select
        sale_location_id as location_id,
        sale_date,
        sum(net_sales_amount) as net_sales_amount,
        count(*) as units_sold
    from {{ ref('stg_sales') }}
    group by 1, 2
)

select
    ld.location_id || '|' || strftime(ld.calendar_date, '%Y-%m-%d') as location_day_id,
    ld.location_id,
    ld.calendar_date as sale_date,
    ld.ly_date,
    ld.is_comp,
    coalesce(ty.net_sales_amount, 0)::decimal(18, 2) as ty_net_sales_amount,
    coalesce(ly.net_sales_amount, 0)::decimal(18, 2) as ly_net_sales_amount,
    coalesce(ty.units_sold, 0)::integer as ty_units_sold,
    coalesce(ly.units_sold, 0)::integer as ly_units_sold
from {{ ref('int_location_days') }} as ld
left join daily as ty
    on ld.location_id = ty.location_id and ld.calendar_date = ty.sale_date
left join daily as ly
    on ld.location_id = ly.location_id and ld.ly_date = ly.sale_date
