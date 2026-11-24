"""Package the semantic-layer exports into one JSON file for the React dashboard.

Run `make dashboard-data` (it runs `make scorecard` first). This reads the CSVs that
`mf query --saved-query ...` wrote to exports/, plus each metric's label, description and owner
from the semantic manifest, and writes ../dashboard/src/data/atelier.json.

The dashboard does no metric math of its own. Every number it shows comes from a governed saved
query, so it agrees with the agent and the parity tests by construction. The output is
deterministic (no timestamps, rounded floats, stable ordering) so CI can check that the committed
file matches a fresh export.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import duckdb

from atelier.paths import PROJECT_DIR, SEMANTIC_MANIFEST_PATH, WAREHOUSE_PATH

EXPORTS_DIR = PROJECT_DIR / "exports"
OUTPUT_PATH = PROJECT_DIR.parent / "dashboard" / "src" / "data" / "atelier.json"

SAVED_QUERIES = [
    "executive_scorecard",
    "inventory_health",
    "sales_trend",
    "category_mix",
    "margin_by_location",
]

# Rename MetricFlow's qualified column names to something friendlier for the front end.
COLUMN_NAMES = {
    "metric_time__fiscal_year": "fiscal_year",
    "metric_time__month": "month",
    "stock_pool__stock_pool_name": "stock_pool",
    "location__channel": "channel",
    "piece__model_category": "model_category",
    "location__location_name": "location",
}
TEXT_COLUMNS = {"fiscal_year", "month", "stock_pool", "channel", "model_category", "location"}


def _value(column: str, raw: str) -> str | float | None:
    if column in TEXT_COLUMNS:
        return raw[:10] if column == "month" else raw  # 2021-06-01T00:00:00 -> 2021-06-01
    if raw in ("", "nan", "None"):
        return None
    number = float(raw)
    if math.isnan(number):
        return None
    return round(number, 6)


def read_export(name: str) -> list[dict]:
    path = EXPORTS_DIR / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"{path} is missing. Run `make scorecard` first.")
    with path.open(newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            clean = {}
            for column, raw in row.items():
                key = COLUMN_NAMES.get(column, column)
                clean[key] = _value(key, raw)
            rows.append(clean)
    sort_keys = [k for k in ("fiscal_year", "month", "stock_pool", "channel", "model_category", "location")
                 if rows and k in rows[0]]
    return sorted(rows, key=lambda r: tuple(str(r[k]) for k in sort_keys))


def metric_definitions(used: set[str]) -> dict[str, dict]:
    manifest = json.loads(SEMANTIC_MANIFEST_PATH.read_text())
    definitions = {}
    for metric in manifest["metrics"]:
        if metric["name"] not in used:
            continue
        meta = (metric.get("config") or {}).get("meta") or {}
        definitions[metric["name"]] = {
            "label": metric.get("label") or metric["name"],
            "description": " ".join((metric.get("description") or "").split()),
            "owner": meta.get("owner"),
            "certified": bool(meta.get("certified")),
        }
    return dict(sorted(definitions.items()))


def data_window() -> dict[str, str]:
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        first, last = con.execute("select min(sale_date), max(sale_date) from marts.fct_sales").fetchone()
    finally:
        con.close()
    return {"first_sale_date": first.isoformat(), "last_sale_date": last.isoformat()}


def main() -> None:
    datasets = {name: read_export(name) for name in SAVED_QUERIES}
    used = {column for rows in datasets.values() for row in rows[:1] for column in row}
    payload = {
        "source": "MetricFlow saved queries in atelier_analytics/models/semantic/saved_queries.yml",
        "data_window": data_window(),
        "metrics": metric_definitions(used),
        **datasets,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=1) + "\n")
    rows = sum(len(r) for r in datasets.values())
    print(f"Wrote {rows} rows from {len(datasets)} saved queries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
