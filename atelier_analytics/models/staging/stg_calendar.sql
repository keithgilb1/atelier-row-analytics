select
    calendar_date,
    calendar_year,
    calendar_month_number,
    calendar_month as calendar_month_name,
    date_trunc('month', calendar_date)::date as calendar_month_start,
    fiscal_year,
    fiscal_quarter,
    fiscal_month_number,
    fiscal_month as fiscal_month_name,
    -- Fiscal months line up with calendar months (FY starts 1 July), so the fiscal month start is the calendar month start.
    date_trunc('month', calendar_date)::date as fiscal_month_start,
    'FY' || fiscal_year::varchar as fiscal_year_label,
    'FY' || fiscal_year::varchar || '-' || fiscal_quarter as fiscal_quarter_label
from {{ source('raw', 'calendar') }}
