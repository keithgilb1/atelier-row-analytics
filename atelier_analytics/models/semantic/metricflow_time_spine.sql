-- Day-grain time spine for the semantic layer, carrying the fiscal calendar as custom granularities.
select
    date_day,
    fiscal_year_label as fiscal_year,
    fiscal_quarter_label as fiscal_quarter
from {{ ref('dim_date') }}
