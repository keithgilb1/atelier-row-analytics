-- One row per stock pool per model category per day.
-- opening + received - sold = closing, and closing today = opening tomorrow (both tested).
with snap as (
    select
        s.snapshot_date,
        s.stock_location_id,
        pr.model_category,
        p.acquisition_cost,
        s.is_sold_today,
        s.snapshot_date = p.floor_date as is_floor_day,
        p.is_opening_stock,
        datediff('day', p.floor_date, s.snapshot_date) as age_days
    from {{ ref('stg_inventory_snapshot') }} as s
    inner join {{ ref('int_pieces') }} as p on s.inventory_id = p.inventory_id
    inner join {{ ref('stg_product_detail') }} as pr on s.inventory_id = pr.inventory_id
),

agg as (
    select
        snapshot_date as inventory_date,
        stock_location_id as stock_pool_location_id,
        model_category,
        count(*) filter (where not is_floor_day or (is_opening_stock and snapshot_date = date '{{ var("history_start_date") }}')) as opening_units,
        count(*) filter (where is_floor_day and not (is_opening_stock and snapshot_date = date '{{ var("history_start_date") }}')) as received_units,
        count(*) filter (where is_sold_today) as sold_units,
        count(*) filter (where not is_sold_today) as closing_units,
        coalesce(sum(acquisition_cost) filter (where not is_sold_today), 0) as closing_cost_amount,
        count(*) filter (where not is_sold_today and age_days > {{ var('aged_inventory_days') }}) as aged_closing_units
    from snap
    group by 1, 2, 3
),

-- Keep a row for every pool x category x day, so on-hand is zero (not missing) on empty days.
spine as (
    select d.calendar_date as inventory_date, l.location_id as stock_pool_location_id, c.model_category
    from {{ ref('stg_calendar') }} as d
    cross join (select distinct stock_pool_location_id as location_id from {{ ref('stg_locations') }}) as l
    cross join (select distinct model_category from {{ ref('stg_product_detail') }}) as c
    where d.calendar_date between date '{{ var("history_start_date") }}' and date '{{ var("as_of_date") }}'
)

select
    s.stock_pool_location_id || '|' || s.model_category || '|' || strftime(s.inventory_date, '%Y-%m-%d') as inventory_day_id,
    s.inventory_date,
    s.stock_pool_location_id,
    s.model_category,
    coalesce(a.opening_units, 0)::integer as opening_units,
    coalesce(a.received_units, 0)::integer as received_units,
    coalesce(a.sold_units, 0)::integer as sold_units,
    coalesce(a.closing_units, 0)::integer as closing_units,
    coalesce(a.closing_cost_amount, 0)::decimal(18, 2) as closing_cost_amount,
    coalesce(a.aged_closing_units, 0)::integer as aged_closing_units
from spine as s
left join agg as a
    on s.inventory_date = a.inventory_date
   and s.stock_pool_location_id = a.stock_pool_location_id
   and s.model_category = a.model_category
