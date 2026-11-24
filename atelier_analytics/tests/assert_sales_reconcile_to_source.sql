-- Sales units and dollars must match the source system exactly, in every mart that carries them.
with source_ as (
    select count(*) as units, sum(sales_price::decimal(18, 2)) as amount from {{ source('raw', 'sales') }}
),
fct as (
    select count(*) as units, sum(net_sales_amount) as amount from {{ ref('fct_sales') }}
),
comp as (
    select sum(ty_units_sold) as units, sum(ty_net_sales_amount) as amount from {{ ref('fct_comp_sales_daily') }}
),
inv as (
    select sum(sold_units) as units from {{ ref('fct_inventory_daily') }}
)

select *
from source_, fct, comp, inv
where fct.units <> source_.units or fct.amount <> source_.amount
   or comp.units <> source_.units or comp.amount <> source_.amount
   or inv.units <> source_.units
