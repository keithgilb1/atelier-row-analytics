-- Every stock row must balance (opening + received - sold = closing) and hand its closing to the next day's opening.
with rows_ as (
    select
        *,
        lead(opening_units) over (
            partition by stock_pool_location_id, model_category order by inventory_date
        ) as next_opening_units
    from {{ ref('fct_inventory_daily') }}
)

select *
from rows_
where opening_units + received_units - sold_units <> closing_units
   or (next_opening_units is not null and next_opening_units <> closing_units)
