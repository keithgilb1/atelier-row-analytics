"""Proof that the governed metrics give one answer, whoever asks.

Consumer A, the dashboard export: `mf query --saved-query ...`, the MetricFlow CLI, the same path a BI
connector takes. Consumer B, the AI agent: its query_metrics tool, which calls MetricFlow's Python
engine from atelier.semantic_layer. An independent pandas implementation from the raw CSVs checks
that the definition itself is implemented correctly. The last test shows the answer an analyst gets
from a plausible hand-written query, and why the governed layer exists.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from atelier import warehouse
from atelier.agent.tools import Toolbox
from atelier.paths import PROJECT_DIR, RAW_DATA_DIR
from parity import reference

MF = str(Path(sys.executable).parent / "mf")
TOL = 1e-9


def close(a, b) -> bool:
    if a is None or b is None or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return (a is None or a != a) and (b is None or b != b)
    return math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=TOL)


def dashboard_export(saved_query: str, tmp_path: Path) -> list[dict]:
    out = tmp_path / f"{saved_query}.csv"
    subprocess.run([MF, "query", "--saved-query", saved_query, "--csv", str(out)],
                   cwd=PROJECT_DIR, check=True, capture_output=True)
    with out.open() as f:
        return [{k: (float(v) if k.startswith(("net", "units", "gross", "average", "comp", "sell", "aged", "inventory")) else v)
                 for k, v in r.items()} for r in csv.DictReader(f)]


def agent_tool(metrics: list[str], group_by: list[str]) -> list[dict]:
    content, is_error = Toolbox().execute(
        "query_metrics", {"metrics": metrics, "group_by": group_by, "where": [], "order_by": [], "limit": 1000}
    )
    assert not is_error, content
    payload = json.loads(content)
    return [dict(zip(payload["columns"], r)) for r in payload["rows"]]


@pytest.fixture(scope="module")
def raw():
    if not (RAW_DATA_DIR / "sales.csv").exists():
        pytest.skip("raw CSVs not generated")
    return reference.load(RAW_DATA_DIR)


SCORECARD_METRICS = ["net_sales", "units_sold", "gross_margin_pct", "average_selling_price",
                     "comp_store_sales_growth", "comp_sales_growth", "average_days_to_sell"]


def test_dashboard_and_agent_agree_on_the_executive_scorecard(tmp_path):
    dash = {r["metric_time__fiscal_year"]: r for r in dashboard_export("executive_scorecard", tmp_path)}
    agent = {r["metric_time__fiscal_year"]: r for r in agent_tool(SCORECARD_METRICS, ["metric_time__fiscal_year"])}
    assert set(dash) == set(agent) and len(dash) >= 6
    for fy in dash:
        for m in SCORECARD_METRICS:
            assert close(dash[fy][m], agent[fy][m]), (fy, m, dash[fy][m], agent[fy][m])


def test_dashboard_and_agent_agree_on_inventory_health(tmp_path):
    metrics = ["sell_through_rate", "units_on_hand", "aged_inventory_share", "inventory_cost_on_hand"]
    key = ("metric_time__fiscal_year", "stock_pool__stock_pool_name")
    dash = {tuple(r[k] for k in key): r for r in dashboard_export("inventory_health", tmp_path)}
    agent = {tuple(r[k] for k in key): r for r in agent_tool(metrics, list(key))}
    assert set(dash) == set(agent) and len(dash) >= 18
    for k in dash:
        for m in metrics:
            assert close(dash[k][m], agent[k][m]), (k, m)


def test_comp_growth_matches_independent_recompute(raw):
    governed = {r["metric_time__fiscal_year"]: r for r in
                agent_tool(["comp_store_sales_growth", "comp_sales_growth"], ["metric_time__fiscal_year"])}
    stores = reference.comp_store_sales_growth_by_fy(raw)
    total = reference.comp_store_sales_growth_by_fy(raw, include_online=True)
    assert len(stores) >= 5
    for fy in stores.index:
        assert close(governed[fy]["comp_store_sales_growth"], stores[fy]), fy
        assert close(governed[fy]["comp_sales_growth"], total[fy]), fy


def test_margin_and_sell_through_match_independent_recompute(raw):
    gm = {r["metric_time__fiscal_year"]: r["gross_margin_pct"] for r in
          agent_tool(["gross_margin_pct"], ["metric_time__fiscal_year"])}
    for fy, v in reference.gross_margin_pct_by_fy(raw).items():
        assert close(gm[fy], v), fy

    pools = {"LOC-NYC": "New York City", "LOC-LA": "Los Angeles", "LOC-MIA": "Miami"}
    st = {(r["metric_time__fiscal_year"], r["stock_pool__stock_pool_name"]): r["sell_through_rate"] for r in
          agent_tool(["sell_through_rate"], ["metric_time__fiscal_year", "stock_pool__stock_pool_name"])}
    ref = reference.sell_through_by_fy_and_pool(raw)
    for (fy, pool), v in ref.items():
        assert close(st[(fy, pools[pool])], v), (fy, pool)


def test_hand_written_sql_gets_a_different_answer():
    """The question: "How are FY2027 comps tracking?" asked without the semantic layer."""
    governed = {r["metric_time__fiscal_year"]: r["comp_store_sales_growth"]
                for r in agent_tool(["comp_store_sales_growth"], ["metric_time__fiscal_year"])}["FY2027"]

    con = warehouse.connect()
    try:
        # Naive 1: full FY2027 to date against all of FY2026. Compares 5 months with 12.
        naive_full_year = con.execute("""
            select sum(net_sales_amount) filter (where d.fiscal_year = 2027)
                 / sum(net_sales_amount) filter (where d.fiscal_year = 2026) - 1
            from marts.fct_sales s join marts.dim_date d on d.date_day = s.sale_date
        """).fetchone()[0]
        # Naive 2: same calendar window, but every location including online, and Feb 29 not handled.
        naive_ytd_all_channels = con.execute("""
            select sum(net_sales_amount) filter (where sale_date between '2026-07-01' and '2026-11-21')
                 / sum(net_sales_amount) filter (where sale_date between '2025-07-01' and '2025-11-21') - 1
            from marts.fct_sales
        """).fetchone()[0]
    finally:
        con.close()

    print(f"\nFY2027 comp store sales growth, governed: {governed:+.2%}")
    print(f"Naive, FY2027 YTD vs all of FY2026:      {float(naive_full_year):+.2%}")
    print(f"Naive, YTD vs LY, online included:       {float(naive_ytd_all_channels):+.2%}")
    assert float(naive_full_year) < -0.5          # looks like a collapse
    assert abs(float(naive_ytd_all_channels) - governed) > 0.01  # a different headline
