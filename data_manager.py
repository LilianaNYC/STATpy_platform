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


def load_portfolio(cfg: dict, base_dir: Path) -> pd.DataFrame:
    """Load the portfolio Excel file, clean null sentinels, derive quarter labels."""
    path = base_dir / cfg["data"]["portfolio_file"]
    sheet = cfg["data"].get("portfolio_sheet_name") or cfg["data"].get("sheet_name")
    if not sheet:
        raise KeyError("Missing portfolio sheet name in config: set data.portfolio_sheet_name or data.sheet_name")

    log.info("Loading portfolio from %s [%s]", path, sheet)

    df = pd.read_excel(path, sheet_name=sheet)

    # Replace null sentinels with actual NaN
    sentinels = cfg["data"].get("null_sentinels", ["NULL", "ZZZ", "N/A", ""])
    df.replace(sentinels, pd.NA, inplace=True)

    # Ensure date column is datetime
    date_col = cfg["data"]["date_column"]
    df[date_col] = pd.to_datetime(df[date_col])

    # Add quarter label column
    df["_quarter"] = df[date_col].apply(_label)
    df["_snapshot_date"] = df[date_col].dt.date

    log.info("Loaded %d records across %d quarters", len(df), df["_quarter"].nunique())
    return df


def load_schema(cfg: dict, base_dir: Path) -> pd.DataFrame:
    """Load the schema definition file."""
    path = base_dir / cfg["data"]["schema_file"]
    log.info("Loading schema from %s", path)
    schema = pd.read_excel(path, sheet_name="PORT")
    schema.columns = ["variable_name", "data_type", "variable_type", "note", "key_variable", "usage"]
    return schema


def load_monitoring_thresholds(cfg: dict, base_dir: Path) -> dict[str, pd.DataFrame]:
    """Load monitoring threshold sheets from the thresholds workbook."""
    path = base_dir / cfg["data"]["monitoring_thresholds_file"]
    log.info("Loading monitoring thresholds from %s", path)

    thresholds: dict[str, pd.DataFrame] = {}

    for key, sheet_name in cfg["data"].items():
        if not isinstance(key, str) or not (
            key.endswith("_thresholds_sheet_name") or key == "crr_master_scale_sheet_name"
        ):
            continue
        if not sheet_name:
            continue

        dict_key = key[: -len("_sheet_name")]  # pd_thresholds_sheet_name -> pd_thresholds

        try:
            df = pd.read_excel(path, sheet_name=sheet_name)
            thresholds[dict_key] = df
            log.info("Loaded thresholds sheet '%s' as %s (%d rows, %d cols)",
                     sheet_name, dict_key, len(df), len(df.columns))
        except Exception as exc:
            log.warning("Unable to load sheet '%s' for %s: %s", sheet_name, dict_key, exc)
            thresholds[dict_key] = pd.DataFrame()

    log.info("Monitoring thresholds loaded: %s", list(thresholds.keys()))
    return thresholds


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
