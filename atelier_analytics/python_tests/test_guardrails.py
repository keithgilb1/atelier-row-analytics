import pytest

from atelier import warehouse
from atelier.agent.guardrails import GuardrailViolation, check_sql

ALLOWED = [
    "select count(*) from fct_sales",
    "select location_id, sum(net_sales_amount) from marts.fct_sales group by 1",
    "with x as (select * from fct_sales) select count(*) from x",
    "select s.location_id, l.channel from fct_sales s join dim_location l using (location_id)",
]

BLOCKED = {
    "delete from marts.fct_sales": "Only SELECT",
    "update marts.fct_sales set net_sales_amount = 0": "Only SELECT",
    "drop table marts.fct_sales": "Only SELECT",
    "select 1; drop table marts.fct_sales": "exactly one",
    "select * from raw.main.customers": "outside the marts schema",
    "select * from staging.stg_customers": "outside the marts schema",
    "select * from audit.audit_sale_price_outliers": "outside the marts schema",
    "select * from information_schema.columns": "outside the marts schema",
    "select * from read_csv('/etc/passwd')": "Table functions",
    "select * from 'data.parquet'": "not an approved mart",
    "select getenv('HOME')": "getenv",
    "copy marts.fct_sales to 'out.csv'": "Only SELECT",
    "attach 'other.duckdb'": "Only SELECT",
    "install httpfs": "Only SELECT",
    "pragma database_list": "Only SELECT",
    "this is not sql": "parse|Only SELECT",
}


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_queries_pass_and_get_a_limit(sql):
    checked = check_sql(sql)
    assert "LIMIT" in checked.sql.upper()
    assert "marts." in checked.sql


def test_existing_small_limit_is_kept_and_large_one_capped():
    assert check_sql("select * from fct_sales limit 5").sql.endswith("LIMIT 5")
    assert check_sql("select * from fct_sales limit 999999").sql.endswith("LIMIT 1000")


@pytest.mark.parametrize("sql,reason", BLOCKED.items())
def test_unsafe_queries_are_blocked(sql, reason):
    with pytest.raises(GuardrailViolation, match=reason):
        check_sql(sql)


def test_connection_is_read_only_even_if_a_check_were_missed():
    con = warehouse.connect()
    try:
        with pytest.raises(Exception):
            con.execute("create table marts.x as select 1")
        with pytest.raises(Exception):
            con.execute("select * from read_csv('/etc/hostname')").fetchall()
    finally:
        con.close()
