-- Governance: no column that looks like personal data may appear in the public marts or the semantic layer.
select table_schema, table_name, column_name
from information_schema.columns
where table_catalog = current_database()
  and table_schema = 'marts'
  and regexp_matches(lower(column_name), 'customer_name|address|phone|birthday|email')
