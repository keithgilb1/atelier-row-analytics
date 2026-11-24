"""Filesystem locations, overridable with environment variables."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
WAREHOUSE_PATH = Path(os.environ.get("ATELIER_DBT_DB", PROJECT_DIR / "atelier_analytics.duckdb"))
SEMANTIC_MANIFEST_PATH = PROJECT_DIR / "target" / "semantic_manifest.json"
RAW_DATA_DIR = Path(
    os.environ.get("ATELIER_RAW_DIR", PROJECT_DIR.parent / "generator" / "atelier_row_data")
)
AGENT_LOG_DIR = Path(os.environ.get("ATELIER_AGENT_LOG_DIR", PROJECT_DIR / "agent" / "logs"))
