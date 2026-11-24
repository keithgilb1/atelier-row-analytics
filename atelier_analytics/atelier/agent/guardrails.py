"""Guardrails for ad-hoc SQL written by the agent.

The governed path (query_metrics) never needs these: MetricFlow writes that SQL. These checks apply to
run_sql, the fallback for questions no certified metric answers. Every check fails closed.

1. Exactly one statement, and it must be a SELECT (CTEs allowed).
2. Only tables in the public `marts` schema. Staging, the raw source, the audit schema and system
   catalogs are off limits.
3. No functions that read files, reach the network or change state (read_csv, read_parquet, glob, ...).
4. A row limit is always applied.
5. Execution happens on a read-only connection with a timeout (see tools.py), so even a check that
   missed something cannot change data.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

ALLOWED_SCHEMA = "marts"
ALLOWED_TABLES = frozenset(
    {
        "dim_date",
        "dim_location",
        "dim_product",
        "dim_customer",
        "fct_sales",
        "fct_purchases",
        "fct_comp_sales_daily",
        "fct_inventory_daily",
    }
)
BLOCKED_FUNCTIONS = frozenset(
    {
        "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto", "read_text",
        "read_blob", "glob", "parquet_scan", "csv_scan", "sniff_csv", "query_table", "query",
        "getenv", "current_setting", "pragma", "duckdb_settings", "duckdb_secrets", "sql_auto_complete",
    }
)
MAX_ROWS = 1000


class GuardrailViolation(ValueError):
    """Raised when agent-written SQL breaks a rule. The message is returned to the model."""


@dataclass(frozen=True)
class CheckedSql:
    sql: str
    tables: tuple[str, ...]


def check_sql(sql: str, max_rows: int = MAX_ROWS) -> CheckedSql:
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise GuardrailViolation(f"SQL did not parse: {e}") from None

    if len(statements) != 1:
        raise GuardrailViolation("Send exactly one SQL statement.")
    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise GuardrailViolation(f"Only SELECT queries are allowed, got {stmt.key.upper()}.")

    for node in stmt.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
                             exp.Command, exp.Copy, exp.Attach, exp.Detach, exp.Pragma, exp.Set)):
            raise GuardrailViolation(f"{node.key.upper()} is not allowed.")

    cte_names = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
    tables: list[str] = []
    for t in stmt.find_all(exp.Table):
        name = t.name.lower()
        if not name:
            # A table function such as read_csv('...') in the FROM clause.
            raise GuardrailViolation("Table functions are not allowed in FROM.")
        if name in cte_names and not t.db:
            continue
        schema = (t.db or "").lower()
        catalog = (t.catalog or "").lower()
        if schema not in ("", ALLOWED_SCHEMA) or catalog not in ("", "atelier_analytics"):
            raise GuardrailViolation(
                f"Table {t.sql()} is outside the marts schema. Only marts.* tables can be queried."
            )
        if name not in ALLOWED_TABLES:
            raise GuardrailViolation(
                f"Table {name} is not an approved mart. Approved: {', '.join(sorted(ALLOWED_TABLES))}."
            )
        tables.append(name)

    for fn in stmt.find_all(exp.Func):
        fname = (fn.sql_name() if not isinstance(fn, exp.Anonymous) else fn.name).lower()
        if fname in BLOCKED_FUNCTIONS:
            raise GuardrailViolation(f"Function {fname} is not allowed.")

    # Qualify bare table names with the marts schema and enforce the row limit.
    for t in stmt.find_all(exp.Table):
        if t.name.lower() in ALLOWED_TABLES and not t.db:
            t.set("db", exp.to_identifier(ALLOWED_SCHEMA))
    existing = stmt.args.get("limit")
    if existing is None or _limit_value(existing) is None or _limit_value(existing) > max_rows:
        stmt = stmt.limit(max_rows)

    return CheckedSql(sql=stmt.sql(dialect="duckdb"), tables=tuple(sorted(set(tables))))


def _limit_value(limit_node: exp.Expression) -> int | None:
    expr = limit_node.args.get("expression")
    if isinstance(expr, exp.Literal) and expr.is_int:
        return int(expr.this)
    return None
