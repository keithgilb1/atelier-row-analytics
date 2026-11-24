"""Tools the agent can call. Each returns a JSON-serialisable dict and records what it ran."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from atelier import semantic_layer, warehouse
from atelier.agent.guardrails import ALLOWED_TABLES, GuardrailViolation, check_sql

QUERY_TIMEOUT_SECONDS = 20
TIME_GRAINS = ["day", "week", "month", "quarter", "year", "fiscal_quarter", "fiscal_year"]


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, float) and v != v:  # NaN
        return None
    return v


def _rows(columns: list[str], rows: list[tuple], cap: int = 200) -> dict:
    return {
        "columns": columns,
        "rows": [[_jsonable(v) for v in r] for r in rows[:cap]],
        "row_count": len(rows),
        "truncated": len(rows) > cap,
    }


def _run_with_timeout(fn: Callable[[], Any], con) -> Any:
    timer = threading.Timer(QUERY_TIMEOUT_SECONDS, con.interrupt)
    timer.start()
    try:
        return fn()
    finally:
        timer.cancel()


@dataclass
class ToolCallRecord:
    tool: str
    input: dict
    sql: str | None = None
    row_count: int | None = None
    error: str | None = None
    path: str | None = None  # "governed" or "ad_hoc"


@dataclass
class AnswerSubmission:
    answer: str
    headline_value: float | None
    unit: str | None
    metrics_used: list[str]
    caveats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------- tool schemas

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "list_metrics",
        "description": (
            "List the certified business metrics in the governed semantic layer, with their definitions "
            "and owners. Call this first for any question about sales, comps, margin, inventory or "
            "sell-through."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "list_dimensions",
        "description": (
            "List the group-by names valid for a set of metrics. Time can always be grouped as "
            "metric_time__<grain> where grain is one of: " + ", ".join(TIME_GRAINS) + "."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"metrics": {"type": "array", "items": {"type": "string"}}},
            "required": ["metrics"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "query_metrics",
        "description": (
            "Query certified metrics through the semantic layer. This is the governed path: the SQL is "
            "generated from the single metric definition, so the number matches every dashboard. "
            "group_by uses names like metric_time__fiscal_year or location__location_name. "
            "where uses MetricFlow syntax, for example "
            "\"{{ TimeDimension('metric_time', 'day') }} >= '2025-07-01'\" or "
            "\"{{ Dimension('location__channel') }} = 'Store'\". "
            "order_by takes group-by or metric names, prefix with - for descending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metrics": {"type": "array", "items": {"type": "string"}},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "where": {"type": "array", "items": {"type": "string"}},
                "order_by": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
            },
            "required": ["metrics", "group_by", "where", "order_by", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "describe_tables",
        "description": "Show the columns of the approved mart tables, for questions no certified metric covers.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "run_sql",
        "description": (
            "Run one read-only DuckDB SELECT against the approved marts (schema marts). Use only when no "
            "certified metric answers the question, and say in the answer that the figure is ad hoc, "
            "not a certified metric. Never use it to recompute a certified metric."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "submit_answer",
        "description": (
            "Finish by submitting the answer. Always call this exactly once, as your last action. "
            "headline_value is the single number that answers the question, as a plain number "
            "(a growth rate of 6.3% is 0.063, and $1.2M is 1200000), or null if there is none."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Plain-English answer for a business reader."},
                "headline_value": {"type": ["number", "null"]},
                "unit": {"type": ["string", "null"], "description": "usd, ratio, units, days or null"},
                "metrics_used": {"type": "array", "items": {"type": "string"}},
                "caveats": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["answer", "headline_value", "unit", "metrics_used", "caveats"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ---------------------------------------------------------------------------- tool execution

class Toolbox:
    def __init__(self) -> None:
        self.calls: list[ToolCallRecord] = []
        self.submission: AnswerSubmission | None = None

    def execute(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Run a tool. Returns (content for the tool_result block, is_error)."""
        record = ToolCallRecord(tool=name, input=tool_input)
        self.calls.append(record)
        try:
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                raise GuardrailViolation(f"Unknown tool {name}.")
            result = handler(record, **tool_input)
            return json.dumps(result, default=_jsonable), False
        except (GuardrailViolation, ValueError) as e:
            record.error = str(e)
            return f"Error: {e}", True
        except Exception as e:  # database errors, MetricFlow errors - returned to the model to fix
            record.error = f"{type(e).__name__}: {e}"
            return f"Error: {type(e).__name__}: {str(e)[:1500]}", True

    def _tool_list_metrics(self, record: ToolCallRecord) -> dict:
        return {
            "metrics": [
                {"name": m.name, "label": m.label, "description": m.description, "owner": m.owner,
                 "certified": m.certified}
                for m in semantic_layer.catalog().values()
                if m.certified
            ],
            "time_grains": TIME_GRAINS,
        }

    def _tool_list_dimensions(self, record: ToolCallRecord, metrics: list[str]) -> dict:
        return {"group_by": semantic_layer.dimensions_for(metrics),
                "time": [f"metric_time__{g}" for g in TIME_GRAINS]}

    def _tool_query_metrics(self, record: ToolCallRecord, metrics, group_by, where, order_by, limit) -> dict:
        record.path = "governed"
        limit = min(int(limit or 200), 1000)
        sql = semantic_layer.compile_sql(metrics, group_by, where, order_by, limit)
        record.sql = sql
        con = warehouse.connect()
        try:
            result = _run_with_timeout(lambda: warehouse.run(sql, con=con, max_rows=limit), con)
        finally:
            con.close()
        record.row_count = len(result.rows)
        return _rows(result.columns, result.rows)

    def _tool_describe_tables(self, record: ToolCallRecord) -> dict:
        con = warehouse.connect()
        try:
            rows = con.execute(
                "select table_name, column_name, data_type from information_schema.columns "
                "where table_schema = 'marts' order by table_name, ordinal_position"
            ).fetchall()
        finally:
            con.close()
        out: dict[str, list[str]] = {}
        for t, c, d in rows:
            if t in ALLOWED_TABLES:
                out.setdefault(f"marts.{t}", []).append(f"{c} {d}")
        return out

    def _tool_run_sql(self, record: ToolCallRecord, sql: str) -> dict:
        record.path = "ad_hoc"
        checked = check_sql(sql)
        record.sql = checked.sql
        con = warehouse.connect()
        try:
            result = _run_with_timeout(lambda: warehouse.run(checked.sql, con=con), con)
        finally:
            con.close()
        record.row_count = len(result.rows)
        return _rows(result.columns, result.rows)

    def _tool_submit_answer(self, record: ToolCallRecord, answer, headline_value, unit, metrics_used, caveats) -> dict:
        self.submission = AnswerSubmission(
            answer=answer, headline_value=headline_value, unit=unit,
            metrics_used=list(metrics_used), caveats=list(caveats),
        )
        return {"status": "received"}
