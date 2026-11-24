"""Read-only access to the built warehouse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from atelier.paths import WAREHOUSE_PATH


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


def connect() -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only, with file and network access switched off.

    Nothing that goes through this connection can change data, read local files or reach the network.
    """
    return duckdb.connect(
        str(WAREHOUSE_PATH),
        read_only=True,
        config={"enable_external_access": False, "lock_configuration": True},
    )


def run(sql: str, con: duckdb.DuckDBPyConnection | None = None, max_rows: int = 1000) -> QueryResult:
    own = con is None
    con = con or connect()
    try:
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        return QueryResult(columns=columns, rows=rows)
    finally:
        if own:
            con.close()
