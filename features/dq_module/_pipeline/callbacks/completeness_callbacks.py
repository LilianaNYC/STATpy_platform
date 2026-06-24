"""Completeness page data builders — by segment / type / source system + schema enrichment."""

from __future__ import annotations

import pandas as pd

from ..config.dashboard_config import SOURCE_SYSTEMS


def _safe_str(v) -> str:
    """Coerce a value to a clean string, treating NaN/None/empty as '—'."""
    if v is None:
        return "—"
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return "—"
    return s


def enrich_with_schema(by_column: list[dict], schema_df: pd.DataFrame) -> list[dict]:
    """Annotate each row in `by_column` with schema metadata so the front-end
    can filter by key/non-key, data type, usage, etc."""
    if schema_df is None or schema_df.empty:
        return by_column
    lookup = schema_df.set_index("variable_name").to_dict("index")
    for row in by_column:
        meta = lookup.get(row["column"], {}) or {}
        row["is_key_var"]      = str(meta.get("key_variable", "")).strip().upper() == "Y"
        row["variable_type"]   = _safe_str(meta.get("variable_type"))
        row["schema_dtype"]    = _safe_str(meta.get("data_type"))
        row["usage"]           = _safe_str(meta.get("usage"))
    return by_column


def build_by_segment(df: pd.DataFrame, seg_col: str = "BUSINESS UNIT") -> list[dict]:
    if seg_col not in df.columns:
        return []
    results = []
    data_cols = [c for c in df.columns if not c.startswith("_")]
    for seg in sorted(df[seg_col].dropna().unique()):
        seg_df = df[df[seg_col] == seg][data_cols]
        n_vals = seg_df.size
        n_missing = int(seg_df.isna().sum().sum())
        completeness = round((1 - n_missing / n_vals) * 100, 2) if n_vals > 0 else 100.0
        results.append({
            "segment": seg,
            "completeness_pct": completeness,
            "missing_pct": round(100 - completeness, 2),
        })
    return results


def build_by_type(df: pd.DataFrame, schema_df: pd.DataFrame) -> list[dict]:
    type_map = schema_df.set_index("variable_name")["data_type"].to_dict()
    buckets: dict[str, list] = {}
    for col in df.columns:
        if col.startswith("_"):
            continue
        dt = str(type_map.get(col, "other")).lower()
        label = "Text" if "text" in dt else "Numeric" if "float" in dt or "int" in dt else "Date" if "date" in dt else "Other"
        buckets.setdefault(label, []).append(col)
    result = []
    for label, cols in buckets.items():
        sub = df[cols]
        n_vals = sub.size
        n_miss = int(sub.isna().sum().sum())
        completeness = round((1 - n_miss / n_vals) * 100, 2) if n_vals > 0 else 100.0
        result.append({"type": label, "completeness_pct": completeness, "missing_pct": round(100 - completeness, 2)})
    return result


def build_by_source(df: pd.DataFrame) -> list[dict]:
    """Mock per-source completeness using Balance Source as proxy."""
    if "Balance Source" not in df.columns:
        return []
    data_cols = [c for c in df.columns if not c.startswith("_") and c != "Balance Source"]
    results = []
    for src, label in SOURCE_SYSTEMS.items():
        sub = df[df["Balance Source"] == src]
        if sub.empty:
            continue
        n_vals = sub[data_cols].size
        n_miss = int(sub[data_cols].isna().sum().sum())
        completeness = round((1 - n_miss / n_vals) * 100, 2) if n_vals > 0 else 100.0
        results.append({"source": label, "completeness_pct": completeness, "missing_pct": round(100 - completeness, 2)})
    results.sort(key=lambda r: r["completeness_pct"])
    return results
