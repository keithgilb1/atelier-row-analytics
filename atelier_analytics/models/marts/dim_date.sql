select
    calendar_date as date_day,
    calendar_year,
    calendar_month_number,
    calendar_month_name,
    calendar_month_start,
    fiscal_year,
    fiscal_year_label,
    fiscal_quarter,
    fiscal_quarter_label,
    fiscal_month_number,
    fiscal_month_name,
    fiscal_month_start,
    dayofweek(calendar_date) in (0, 6) as is_weekend
from {{ ref('stg_calendar') }}
