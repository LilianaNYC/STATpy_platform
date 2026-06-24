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


def _portfolio_vs_schema(df: pd.DataFrame, schema_df: pd.DataFrame) -> dict:
    """For one portfolio's data, compute the alignment against the schema definition.

    Returns:
      - missing_from_data:   cols declared in schema but absent from the data file
      - extra_in_data:       cols present in data but not declared in schema
      - type_issues:         cols whose actual dtype doesn't match the declared one
      - coverage_pct:        % of declared schema cols present in the data
    """
    expected = set(schema_df["variable_name"].dropna().astype(str).tolist())
    actual   = set(c for c in df.columns if not c.startswith("_"))

    missing_from_data = sorted(expected - actual)
    extra_in_data     = sorted(actual - expected)

    type_map = schema_df.set_index("variable_name")["data_type"].to_dict()
    type_issues = []
    for col in sorted(actual & expected):
        expected_type = str(type_map.get(col, "") or "").lower()
        actual_dtype  = str(df[col].dtype).lower()
        match = (
            ("float"  in expected_type and "float"    in actual_dtype) or
            ("int"    in expected_type and "int"      in actual_dtype) or
            ("text"   in expected_type and "object"   in actual_dtype) or
            ("date"   in expected_type and "datetime" in actual_dtype) or
            ("decimal" in expected_type and "float"   in actual_dtype)
        )
        if not match:
            type_issues.append({
                "column": col,
                "expected": expected_type or "—",
                "actual": actual_dtype,
            })

    coverage = round(len(expected & actual) / max(len(expected), 1) * 100, 1)

    return {
        "missing_from_data": missing_from_data,
        "extra_in_data":     extra_in_data,
        "type_issues":       type_issues,
        "coverage_pct":      coverage,
        "schema_cols":       len(expected),
        "data_cols":         len(actual),
    }


def _key_var_roster(df25: pd.DataFrame, df24: pd.DataFrame, schema_df: pd.DataFrame) -> list[dict]:
    """One row per key variable (key_variable=Y in schema), with presence flags."""
    cols25 = set(c for c in df25.columns if not c.startswith("_"))
    cols24 = set(c for c in df24.columns if not c.startswith("_"))
    roster = []
    for _, r in schema_df.iterrows():
        if str(r.get("key_variable", "")).strip().upper() != "Y":
            continue
        name = r["variable_name"]
        roster.append({
            "column":        name,
            "in_p24":        name in cols24,
            "in_p25":        name in cols25,
            "data_type":     str(r.get("data_type", "—") or "—"),
            "variable_type": str(r.get("variable_type", "—") or "—"),
            "usage":         str(r.get("usage", "—") or "—"),
        })
    # Sort: missing-in-either first, then alphabetical
    roster.sort(key=lambda x: (x["in_p24"] and x["in_p25"], x["column"]))
    return roster


def _naming_hygiene(df25: pd.DataFrame, df24: pd.DataFrame) -> list[dict]:
    """Detect potential naming issues: trailing whitespace, case-insensitive near-duplicates."""
    findings = []
    all_cols = set(df25.columns) | set(df24.columns)
    all_cols = [c for c in all_cols if not c.startswith("_")]

    # Trailing/leading whitespace
    for c in all_cols:
        if c != c.strip():
            findings.append({"column": c, "issue": "Leading/trailing whitespace"})

    # Case-insensitive duplicates (different cols that match when lowercased)
    lower_map: dict[str, list[str]] = {}
    for c in all_cols:
        lower_map.setdefault(c.lower(), []).append(c)
    for low, variants in lower_map.items():
        if len(variants) > 1:
            findings.append({"column": " ⇔ ".join(variants), "issue": "Case-insensitive duplicate"})

    return findings


def build_schema_diff(df25: pd.DataFrame, df24: pd.DataFrame, schema_df: pd.DataFrame | None = None) -> dict:
    """Column-level diff between port24 and port25 files, plus per-portfolio
    schema-vs-data validation and key-variable roster (if schema_df is provided)."""
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

    result = {
        "port24_columns": len(cols24),
        "port25_columns": len(cols25),
        "added": added,
        "removed": removed,
        "type_changes": type_changes,
        "net_change": len(cols25) - len(cols24),
    }

    if schema_df is not None and not schema_df.empty:
        result["port24_vs_schema"] = _portfolio_vs_schema(df24, schema_df)
        result["port25_vs_schema"] = _portfolio_vs_schema(df25, schema_df)
        result["key_var_roster"]   = _key_var_roster(df25, df24, schema_df)
        result["naming_hygiene"]   = _naming_hygiene(df25, df24)

    return result
