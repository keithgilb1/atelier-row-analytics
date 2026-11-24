"""Python client for the governed semantic layer.

Every consumer in this repo (the scorecard export, the AI agent, the parity tests) asks for metrics by
name through this module. MetricFlow compiles the request from the YAML definitions in
models/semantic/, and the SQL runs on a read-only DuckDB connection. No consumer writes its own
metric SQL, so they can't disagree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest
from metricflow.protocols.sql_client import SqlEngine
from metricflow.sql.render.duckdb_renderer import DuckDbSqlPlanRenderer
from metricflow_semantics.model.dbt_manifest_parser import parse_manifest_from_dbt_generated_manifest
from metricflow_semantics.model.semantic_manifest_lookup import SemanticManifestLookup

from atelier import warehouse
from atelier.paths import SEMANTIC_MANIFEST_PATH


class _CompileOnlySqlClient:
    """MetricFlow needs a SqlClient to know the dialect. We only use it to compile SQL, never to run it."""

    sql_engine_type = SqlEngine.DUCKDB
    sql_plan_renderer = DuckDbSqlPlanRenderer()

    def _refuse(self, *args, **kwargs):  # pragma: no cover - guard
        raise RuntimeError("The semantic layer compiles SQL only. Execution goes through atelier.warehouse.")

    query = execute = dry_run = _refuse

    def close(self) -> None:
        pass

    def render_bind_parameter_key(self, bind_parameter_key: str) -> str:
        return f"${bind_parameter_key}"


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    description: str
    type: str
    owner: str | None
    certified: bool


@dataclass(frozen=True)
class MetricResult:
    sql: str
    columns: list[str]
    rows: list[tuple]

    def as_dicts(self) -> list[dict]:
        return [dict(zip(self.columns, r)) for r in self.rows]


def _manifest_json() -> str:
    if not SEMANTIC_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"{SEMANTIC_MANIFEST_PATH} not found. Run `dbt parse --profiles-dir .` (or `make build`) first."
        )
    return SEMANTIC_MANIFEST_PATH.read_text()


@lru_cache(maxsize=1)
def _engine() -> MetricFlowEngine:
    manifest = parse_manifest_from_dbt_generated_manifest(_manifest_json())
    return MetricFlowEngine(
        semantic_manifest_lookup=SemanticManifestLookup(manifest),
        sql_client=_CompileOnlySqlClient(),
    )


@lru_cache(maxsize=1)
def catalog() -> dict[str, Metric]:
    """Metric definitions as published in the semantic manifest."""
    raw = json.loads(_manifest_json())
    out: dict[str, Metric] = {}
    for m in raw["metrics"]:
        meta = (m.get("config") or {}).get("meta") or {}
        out[m["name"]] = Metric(
            name=m["name"],
            label=m.get("label") or m["name"],
            description=" ".join((m.get("description") or "").split()),
            type=m["type"],
            owner=meta.get("owner"),
            certified=bool(meta.get("certified", False)),
        )
    return out


def dimensions_for(metrics: Sequence[str]) -> list[str]:
    """Group-by names that are valid for all the given metrics."""
    dims = _engine().simple_dimensions_for_metrics(list(metrics))
    names = sorted({d.dunder_name if hasattr(d, "dunder_name") else d.qualified_name for d in dims})
    return names


def compile_sql(
    metrics: Sequence[str],
    group_by: Sequence[str] = (),
    where: Sequence[str] = (),
    order_by: Sequence[str] = (),
    limit: int | None = None,
) -> str:
    request = MetricFlowQueryRequest.create(
        metric_names=list(metrics),
        group_by_names=list(group_by) or None,
        where_constraints=list(where) or None,
        order_by_names=list(order_by) or None,
        limit=limit,
    )
    return _engine().explain(request).sql_statement.sql


def query(
    metrics: Sequence[str],
    group_by: Sequence[str] = (),
    where: Sequence[str] = (),
    order_by: Sequence[str] = (),
    limit: int | None = None,
) -> MetricResult:
    unknown = [m for m in metrics if m not in catalog()]
    if unknown:
        raise ValueError(f"Unknown metric(s): {', '.join(unknown)}. Known: {', '.join(sorted(catalog()))}")
    sql = compile_sql(metrics, group_by, where, order_by, limit)
    result = warehouse.run(sql, max_rows=limit or 10_000)
    return MetricResult(sql=sql, columns=result.columns, rows=result.rows)
