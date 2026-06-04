"""Schema page data builders — type distribution + port24/port25 column diff."""

from __future__ import annotations

import pandas as pd


def build_types_distribution(df: pd.DataFrame, schema_df: pd.DataFrame) -> list[dict]:
    type_map = schema_df.set_index("variable_name")["data_type"].to_dict()
    buckets: dict[str, int] = {
        "VARCHAR / Text": 0, "DECIMAL / Float": 0, "INTEGER": 0, "DATE": 0, "OTHER": 0
    }
    for col in df.columns:
        if col.startswith("_"):
            continue
        dt = str(type_map.get(col, "other")).lower()
        if "text" in dt:
            buckets["VARCHAR / Text"] += 1
        elif "float" in dt:
            buckets["DECIMAL / Float"] += 1
        elif "int" in dt:
            buckets["INTEGER"] += 1
        elif "date" in dt:
            buckets["DATE"] += 1
        else:
            buckets["OTHER"] += 1
    total = sum(buckets.values())
    return [{"type": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in buckets.items() if v > 0]


def build_schema_diff(df25: pd.DataFrame, df24: pd.DataFrame) -> dict:
    """Column-level diff between port24 and port25 files."""
    cols25 = set(c for c in df25.columns if not c.startswith("_"))
    cols24 = set(c for c in df24.columns if not c.startswith("_"))

    added   = sorted(cols25 - cols24)
    removed = sorted(cols24 - cols25)
    common  = cols25 & cols24

    type_changes = []
    for col in sorted(common):
        t24 = str(df24[col].dtype)
        t25 = str(df25[col].dtype)
        if t24 != t25:
            type_changes.append({"column": col, "port24_type": t24, "port25_type": t25})

    return {
        "port24_columns": len(cols24),
        "port25_columns": len(cols25),
        "added": added,
        "removed": removed,
        "type_changes": type_changes,
        "net_change": len(cols25) - len(cols24),
    }
