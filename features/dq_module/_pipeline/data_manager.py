"""Data ingestion: load portfolio and schema files, detect quarters, slice by quarter.

Equivalent to STATpy's `data_manager.py` — owns all I/O against the source files.
"""

from __future__ import annotations

import logging
import pandas as pd
from pathlib import Path

log = logging.getLogger(__name__)


def _label(ts: pd.Timestamp) -> str:
    """Convert a quarter-end timestamp to a label like '2025Q1'."""
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}Q{q}"


def load_portfolio(cfg: dict, base_dir: Path, key: str = "portfolio") -> pd.DataFrame:
    """Load a portfolio snapshot table and normalize it.

    `key` selects which portfolio: "portfolio" (current, Port 2025) or
    "portfolio_2024" (comparison). Source is config-driven:
      data.source: excel  → reads cfg["data"][f"{key}_file"] relative to base_dir
      data.source: sql    → runs cfg["data"]["sql"][f"{key}_query"] through
                            STATpy's data_manager gateway (Windows only)
    Both paths end in _normalize().
    """
    source = cfg["data"].get("source", "excel")
    if source == "excel":
        path = base_dir / cfg["data"][f"{key}_file"]
        sheet = cfg["data"]["sheet_name"]
        log.info("Loading portfolio from %s [%s]", path, sheet)
        raw = pd.read_excel(path, sheet_name=sheet)
    elif source == "sql":
        # Deferred import: only resolvable inside the STATpy repo, and excel
        # mode must never touch it.
        from .sql_source import fetch_portfolio
        raw = fetch_portfolio(cfg, key)
    else:
        raise ValueError(f"data.source must be 'excel' or 'sql', got {source!r}")
    return _normalize(raw, cfg)


def _normalize(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Shared post-load cleanup: null sentinels, datetime coercion, quarter labels."""
    sentinels = cfg["data"].get("null_sentinels", ["NULL", "ZZZ", "N/A", ""])
    df.replace(sentinels, pd.NA, inplace=True)

    date_col = cfg["data"]["date_column"]
    df[date_col] = pd.to_datetime(df[date_col])

    df["_quarter"] = df[date_col].apply(_label)
    df["_snapshot_date"] = df[date_col].dt.date

    log.info("Loaded %d records across %d quarters", len(df), df["_quarter"].nunique())
    return df


def source_label(cfg: dict) -> str:
    """Human-readable data-source label for footers/manifest."""
    if cfg["data"].get("source", "excel") == "sql":
        return f"SQL: {cfg['data']['sql']['database']}"
    return Path(cfg["data"]["portfolio_file"]).name


def load_schema(cfg: dict, base_dir: Path) -> pd.DataFrame:
    """Load the schema definition file."""
    path = base_dir / cfg["data"]["schema_file"]
    log.info("Loading schema from %s", path)
    schema = pd.read_excel(path, sheet_name="PORT")
    schema.columns = ["variable_name", "data_type", "variable_type", "note", "key_variable", "usage"]
    return schema


def get_quarters(df: pd.DataFrame) -> list[str]:
    """Return sorted list of all available quarter labels."""
    date_col = "MONTH END-SNAPSHOT DATE"
    dates = df[date_col].sort_values().unique()
    labels = [_label(pd.Timestamp(d)) for d in dates]
    return sorted(set(labels))


def get_quarter_df(df: pd.DataFrame, quarter: str) -> pd.DataFrame:
    """Return rows for a specific quarter label."""
    return df[df["_quarter"] == quarter].copy()


def get_snapshot_date(df: pd.DataFrame, quarter: str) -> str:
    """Return the snapshot date string for a quarter."""
    rows = df[df["_quarter"] == quarter]
    if rows.empty:
        return ""
    return str(rows["_snapshot_date"].iloc[0])
