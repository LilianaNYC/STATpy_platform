"""Business-Rules data builders — failures by segment / domain."""

from __future__ import annotations

import pandas as pd


def build_segment_failures(df: pd.DataFrame, rules: dict, seg_col: str = "BUSINESS UNIT") -> list[dict]:
    """Failure rate by business segment."""
    if seg_col not in df.columns:
        return []
    seg_results = []
    for seg in sorted(df[seg_col].dropna().unique()):
        seg_df = df[df[seg_col] == seg]
        n = len(seg_df)
        # Approximation: each rule failure is independent
        failed = 0
        for rule in rules["by_rule"]:
            if not rule["passed"]:
                failed += round(rule["failure_rate_pct"] / 100 * n)
        rate = round(failed / n * 100, 2) if n > 0 else 0.0
        seg_results.append({"segment": seg, "failure_rate_pct": rate, "n": n})
    return seg_results


def build_domain_failures(rules: dict) -> list[dict]:
    """Aggregate failure counts by data domain."""
    domain_map: dict[str, dict] = {}
    for r in rules["by_rule"]:
        d = r["domain"]
        if d not in domain_map:
            domain_map[d] = {"failed_records": 0, "total": r["total_records"]}
        domain_map[d]["failed_records"] += r["failed_records"]
    result = []
    for domain, vals in domain_map.items():
        n = vals["total"]
        fr = vals["failed_records"]
        result.append({
            "domain": domain,
            "failed_records": fr,
            "failure_rate_pct": round(fr / n * 100, 4) if n > 0 else 0.0,
        })
    result.sort(key=lambda r: -r["failed_records"])
    return result
