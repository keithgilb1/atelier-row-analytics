-- Governance: name, street address, phone and birthday are PII and are deliberately not selected.
-- Nothing downstream of the source can expose them, including the AI agent.
select
    customer_id,
    profile_create_date,
    customer_city,
    state_province,
    country,
    country_code,
    country_code = 'US' as is_domestic
from {{ source('raw', 'customers') }}
