"""An independent re-implementation of three certified metrics, straight from the raw CSV extracts.

It shares no code with dbt or the semantic layer: plain pandas over the generator's CSV files, written
from the written metric definitions. If the governed numbers and these ever disagree, one of the two
implementations is wrong, and the parity tests fail.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

HISTORY_START = pd.Timestamp("2021-06-01")
AS_OF = pd.Timestamp("2026-11-21")
COMP_MONTHS_OPEN = 13


def fiscal_year(d: pd.Series) -> pd.Series:
    """FY runs July to June, named for the year it ends."""
    return "FY" + (d.dt.year + (d.dt.month >= 7).astype(int)).astype(str)


def load(raw_dir: Path) -> dict[str, pd.DataFrame]:
    def csv(name: str, dates: list[str]) -> pd.DataFrame:
        return pd.read_csv(raw_dir / f"{name}.csv", parse_dates=dates)

    return {
        "locations": csv("locations", ["open_date", "close_date"]),
        "sales": csv("sales", ["sale_date"]),
        "purchasing": csv("purchasing", ["purchase_date"]),
        "inventory": csv("inventory", ["snapshot_date"]),
    }


def comp_store_sales_growth_by_fy(data: dict[str, pd.DataFrame], include_online: bool = False) -> pd.Series:
    locs = data["locations"]
    if not include_online:
        locs = locs[locs["location_id"] != "LOC-ONL"]
    sales = data["sales"]
    daily = sales.groupby(["location_id", "sale_date"])["sales_price"].sum()

    rows = []
    for loc in locs.itertuples():
        first_full = loc.open_date if loc.open_date.day == 1 else (loc.open_date + pd.offsets.MonthBegin(1))
        comp_start = first_full + pd.DateOffset(months=COMP_MONTHS_OPEN)
        for d in pd.date_range(max(HISTORY_START, loc.open_date), AS_OF):
            if d.month == 2 and d.day == 29:
                continue
            ly = d - pd.DateOffset(years=1)
            if d < comp_start or ly < HISTORY_START or ly < loc.open_date:
                continue
            if pd.notna(loc.close_date) and d >= loc.close_date:
                continue
            rows.append((d, daily.get((loc.location_id, d), 0.0), daily.get((loc.location_id, ly), 0.0)))

    df = pd.DataFrame(rows, columns=["d", "ty", "ly"])
    df["fy"] = fiscal_year(df["d"])
    g = df.groupby("fy")[["ty", "ly"]].sum()
    return g["ty"] / g["ly"] - 1


def gross_margin_pct_by_fy(data: dict[str, pd.DataFrame]) -> pd.Series:
    s = data["sales"].merge(data["purchasing"][["inventory_id", "purchase_price"]], on="inventory_id")
    s["fy"] = fiscal_year(s["sale_date"])
    g = s.groupby("fy")[["sales_price", "purchase_price"]].sum()
    return (g["sales_price"] - g["purchase_price"]) / g["sales_price"]


def sell_through_by_fy_and_pool(data: dict[str, pd.DataFrame]) -> pd.Series:
    """sold / (on hand at the start of the period + received in the period), by stock pool."""
    inv = data["inventory"]
    first_day = inv.groupby("inventory_id")["snapshot_date"].transform("min")
    pur = data["purchasing"].set_index("inventory_id")["purchase_date"]
    opening_stock = inv["inventory_id"].map(pur) < HISTORY_START
    inv = inv.assign(
        fy=fiscal_year(inv["snapshot_date"]),
        is_receipt=(inv["snapshot_date"] == first_day) & ~(opening_stock & (inv["snapshot_date"] == HISTORY_START)),
        is_sold=inv["sale_id"].notna(),
    )
    out = {}
    for (fy, pool), g in inv.groupby(["fy", "location_id"]):
        start = g["snapshot_date"].min()
        on_day_one = g[g["snapshot_date"] == start]
        opening = int((~on_day_one["is_receipt"]).sum())
        received = int(g["is_receipt"].sum())
        sold = int(g["is_sold"].sum())
        out[(fy, pool)] = sold / (opening + received)
    return pd.Series(out)
