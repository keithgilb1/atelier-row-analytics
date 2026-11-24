-- One row per selling location per day of history, with its comp-store status.
--
-- Comp rule (written once, here):
--   1. A location joins the comp base on the first day of its (comp_months_open + 1)th month,
--      counting from its first full fiscal month open. With the default of 13 that means
--      13 full months of trading before it counts.
--   2. The same calendar date last year must exist in history, and the location must have been
--      open on it. 29 February has no matching day, so it is never a comp day.
--   3. A closed location leaves the comp base from its close date.
with locations as (
    select
        *,
        case
            when day(open_date) = 1 then open_date
            else (date_trunc('month', open_date) + interval 1 month)::date
        end as first_full_month_start
    from {{ ref('stg_locations') }}
),

days as (
    select calendar_date
    from {{ ref('stg_calendar') }}
    where calendar_date between date '{{ var("history_start_date") }}' and date '{{ var("as_of_date") }}'
)

select
    l.location_id,
    d.calendar_date,
    (d.calendar_date - interval 1 year)::date as ly_date,
    (l.first_full_month_start + to_months({{ var('comp_months_open') }}))::date as comp_start_date,
    (
        d.calendar_date >= (l.first_full_month_start + to_months({{ var('comp_months_open') }}))::date
        and (d.calendar_date - interval 1 year)::date >= date '{{ var("history_start_date") }}'
        and (d.calendar_date - interval 1 year)::date >= l.open_date
        and not (month(d.calendar_date) = 2 and day(d.calendar_date) = 29)
        and (l.close_date is null or d.calendar_date < l.close_date)
    ) as is_comp
from locations as l
cross join days as d
where d.calendar_date >= l.open_date
  and (l.close_date is null or d.calendar_date <= l.close_date)
