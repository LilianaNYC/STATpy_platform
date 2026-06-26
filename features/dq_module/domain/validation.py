"""DQ validation engine: business rules, completeness, schema validation, PSI, drift, population.

Equivalent to STATpy core logic modules — pure computation, no I/O.
"""

from __future__ import annotations

import logging
import math
import numpy as np
import pandas as pd
from typing import Any

from .config import (
    SEVERITY_ORDER,
    DEFAULT_PSI_THRESHOLDS,
    DEFAULT_COMPLETENESS_THRESHOLDS,
)

log = logging.getLogger(__name__)


def _apply_rule(df: pd.DataFrame, rule: dict) -> pd.Series:
    """Return boolean mask: True where the rule FAILS."""
    col = rule["column"]
    rtype = rule["type"]

    if col not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[col]

    if rtype == "not_null":
        return series.isna()

    if rtype == "range_min":
        threshold = float(rule["threshold"])
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.notna() & (numeric < threshold)

    if rtype == "range":
        mn = float(rule["min"])
        mx = float(rule["max"])
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.notna() & ((numeric < mn) | (numeric > mx))

    if rtype == "categorical":
        valid = set(str(v) for v in rule["valid_values"])
        return series.notna() & (~series.astype(str).isin(valid))

    if rtype == "cross_field_implies":
        col_b = rule.get("column_b")
        cond_val = str(rule.get("condition_value", "Y"))
        req_val = str(rule.get("required_value", ""))
        if col_b not in df.columns:
            return pd.Series(False, index=df.index)
        triggered = series.notna() & (series.astype(str) == cond_val)
        wrong = df[col_b].astype(str) != req_val
        return triggered & wrong

    if rtype == "cross_field_implies_positive":
        col_b = rule.get("column_b")
        cond_val = str(rule.get("condition_value", "Y"))
        if col_b not in df.columns:
            return pd.Series(False, index=df.index)
        triggered = series.notna() & (series.astype(str) == cond_val)
        col_b_num = pd.to_numeric(df[col_b], errors="coerce")
        not_positive = col_b_num.isna() | (col_b_num <= 0)
        return triggered & not_positive

    if rtype == "cross_field_gap":
        col_b = rule.get("column_b")
        max_gap = float(rule.get("max_gap", 0.30))
        if col_b not in df.columns:
            return pd.Series(False, index=df.index)
        a = pd.to_numeric(series, errors="coerce")
        b = pd.to_numeric(df[col_b], errors="coerce")
        both_valid = a.notna() & b.notna()
        gap = (a - b).abs()
        return both_valid & (gap > max_gap)

    return pd.Series(False, index=df.index)


def apply_rules(df: pd.DataFrame, rules: list[dict]) -> dict[str, Any]:
    """
    Apply all business rules to a dataframe.
    Returns a dict with per-rule results and aggregate counts.
    """
    results = []
    total_failed_mask = pd.Series(False, index=df.index)

    for rule in rules:
        fail_mask = _apply_rule(df, rule)
        n_fail = int(fail_mask.sum())
        n_total = len(df)
        fail_rate = round(n_fail / n_total * 100, 4) if n_total > 0 else 0.0

        results.append({
            "code": rule["code"],
            "description": rule["description"],
            "severity": rule["severity"],
            "domain": rule.get("domain", "Other"),
            "column": rule["column"],
            "failed_records": n_fail,
            "total_records": n_total,
            "failure_rate_pct": fail_rate,
            "passed": n_fail == 0,
        })
        total_failed_mask = total_failed_mask | fail_mask

    n_critical = sum(1 for r in results if not r["passed"] and r["severity"] == "Critical")
    n_failed_rules = sum(1 for r in results if not r["passed"])
    n_records_failed = int(total_failed_mask.sum())

    return {
        "by_rule": results,
        "total_executed": len(rules),
        "rules_failed": n_failed_rules,
        "rules_passed": len(rules) - n_failed_rules,
        "critical_failures": n_critical,
        "records_failed": n_records_failed,
        "failure_rate_pct": round(n_records_failed / len(df) * 100, 4) if len(df) > 0 else 0.0,
    }


def compute_completeness(df: pd.DataFrame, cfg: dict) -> dict[str, Any]:
    """Compute missing % for every column in df."""
    n = len(df)
    critical_cols = set(cfg.get("completeness", {}).get("critical_columns", []))
    thr = cfg.get("completeness", {}).get("thresholds", DEFAULT_COMPLETENESS_THRESHOLDS)

    rows = []
    for col in df.columns:
        if col.startswith("_"):
            continue
        missing_n = int(df[col].isna().sum())
        missing_pct = round(missing_n / n * 100, 4) if n > 0 else 0.0
        severity = "Very Low"
        if missing_pct >= thr["critical"]:
            severity = "Critical"
        elif missing_pct >= thr["high"]:
            severity = "High"
        elif missing_pct >= thr["medium"]:
            severity = "Medium"
        elif missing_pct >= thr["low"]:
            severity = "Low"

        rows.append({
            "column": col,
            "missing_n": missing_n,
            "missing_pct": missing_pct,
            "severity": severity,
            "is_critical_col": col in critical_cols,
        })

    rows.sort(key=lambda r: -r["missing_pct"])
    n_with_missing = sum(1 for r in rows if r["missing_pct"] > 0)
    total_values = n * len([c for c in df.columns if not c.startswith("_")])
    total_missing = sum(r["missing_n"] for r in rows)
    overall_completeness = round((1 - total_missing / total_values) * 100, 4) if total_values > 0 else 100.0

    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Very Low": 0}
    for r in rows:
        severity_counts[r["severity"]] += 1

    return {
        "overall_pct": overall_completeness,
        "total_records": n,
        "columns_analyzed": len(rows),
        "columns_with_missing": n_with_missing,
        "zero_missing_columns": len(rows) - n_with_missing,
        "high_missing_count": severity_counts["High"] + severity_counts["Critical"],
        "critical_missing_count": severity_counts["Critical"],
        "by_column": rows,
        "severity_counts": severity_counts,
    }


def compute_schema_validation(df: pd.DataFrame, schema_df: pd.DataFrame, prior_df) -> dict:
    """Compare actual columns against schema definition and detect changes vs prior quarter."""
    expected = set(schema_df["variable_name"].dropna().tolist())
    actual = set(c for c in df.columns if not c.startswith("_"))

    missing_cols = sorted(expected - actual)
    new_cols = sorted(actual - expected)

    type_issues = []
    # sorted: set iteration order is hash-randomized per process; keep builds reproducible
    for col in sorted(actual & expected):
        schema_type = schema_df.loc[schema_df["variable_name"] == col, "data_type"].values
        if len(schema_type) == 0:
            continue
        expected_type = str(schema_type[0]).lower()
        actual_dtype = str(df[col].dtype).lower()
        type_match = (
            ("float" in expected_type and "float" in actual_dtype)
            or ("int" in expected_type and "int" in actual_dtype)
            or ("text" in expected_type and "object" in actual_dtype)
            or ("date" in expected_type and "datetime" in actual_dtype)
        )
        if not type_match:
            type_issues.append({"column": col, "expected": expected_type, "actual": actual_dtype})

    prior_cols = set(c for c in (prior_df.columns if prior_df is not None else []) if not c.startswith("_"))
    dropped_cols = sorted(prior_cols - actual) if prior_df is not None else []
    added_cols_vs_prior = sorted(actual - prior_cols) if prior_df is not None else []

    n_cols = len(actual)
    issues = len(missing_cols) + len(type_issues)
    quality_score = round(max(0, 100 - issues * 5), 1)

    return {
        "total_columns": n_cols,
        "expected_columns": len(expected),
        "missing_columns": missing_cols,
        "new_columns": new_cols,
        "type_issues": type_issues,
        "dropped_vs_prior": dropped_cols,
        "added_vs_prior": added_cols_vs_prior,
        "modified_columns": len(type_issues),
        "breaking_changes": len(dropped_cols),
        "tables_with_changes": 1 if (dropped_cols or added_cols_vs_prior or type_issues) else 0,
        "quality_score": quality_score,
    }


def compute_psi(reference: pd.Series, current: pd.Series, bins: int = 5) -> float:
    """Population Stability Index between reference and current distributions."""
    ref = reference.dropna()
    cur = current.dropna()
    if len(ref) < 2 or len(cur) < 2:
        return 0.0
    combined = pd.concat([ref, cur])
    actual_bins = min(bins, max(2, len(combined) // 2))
    try:
        _, edges = np.histogram(combined, bins=actual_bins)
        edges[0] = -np.inf
        edges[-1] = np.inf
        eps = 1e-4
        ref_hist, _ = np.histogram(ref, bins=edges)
        cur_hist, _ = np.histogram(cur, bins=edges)
        ref_pct = (ref_hist + eps) / (len(ref) + eps * actual_bins)
        cur_pct = (cur_hist + eps) / (len(cur) + eps * actual_bins)
        psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
        return round(max(0.0, psi), 4)
    except Exception:
        return 0.0


def psi_level(psi: float, cfg: dict) -> str:
    thr = cfg.get("drift", {}).get("thresholds", DEFAULT_PSI_THRESHOLDS)
    if psi >= thr.get("high", 0.50):
        return "High"
    if psi >= thr.get("moderate", 0.20):
        return "Moderate"
    if psi >= thr.get("minor", 0.10):
        return "Minor"
    return "No Drift"


# ──────────────────────────────────────────────────────────────
# Additional drift tests (run on non-null numeric values only;
# missingness drift belongs to the Completeness tab, not here)
# ──────────────────────────────────────────────────────────────

def compute_ks_test(ref: pd.Series, cur: pd.Series) -> dict:
    """Two-sample Kolmogorov-Smirnov test.

    Compares the empirical CDFs of `ref` and `cur`. Pure-numpy implementation
    (no scipy dependency). Returns the test statistic D and an asymptotic
    two-sided p-value (Kolmogorov-Smirnov / Smirnov approximation).

    Interpretation: p > 0.05 ⇒ we cannot reject "same distribution" ⇒ no drift.
    """
    a = pd.to_numeric(ref, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(cur, errors="coerce").dropna().to_numpy()
    n1, n2 = len(a), len(b)
    if n1 < 5 or n2 < 5:
        return {"statistic": None, "p_value": None}
    a = np.sort(a)
    b = np.sort(b)
    all_vals = np.concatenate([a, b])
    cdf1 = np.searchsorted(a, all_vals, side="right") / n1
    cdf2 = np.searchsorted(b, all_vals, side="right") / n2
    D = float(np.max(np.abs(cdf1 - cdf2)))
    # Asymptotic 2-sided p (Smirnov / Stephens' correction)
    n_eff = (n1 * n2) / (n1 + n2)
    lam = (math.sqrt(n_eff) + 0.12 + 0.11 / math.sqrt(n_eff)) * D
    p = 0.0
    sign = 1.0
    for k in range(1, 101):
        term = sign * math.exp(-2 * k * k * lam * lam)
        p += term
        sign *= -1
        if abs(term) < 1e-12:
            break
    p = max(0.0, min(1.0, 2 * p))
    return {"statistic": round(D, 4), "p_value": round(p, 4)}


def compute_welch_t_test(ref: pd.Series, cur: pd.Series) -> dict:
    """Welch's t-test (unequal-variance, two-sample).

    For two groups, equivalent to one-way ANOVA on means. We label this as
    'ANOVA p-value' in the UI for consistency with the user's vocabulary.
    Two-sided p computed via normal-approximation (df is typically large in
    quarterly portfolio data, so the t→normal approximation is accurate).

    Interpretation: p > 0.05 ⇒ no significant mean difference ⇒ no drift.
    """
    a = pd.to_numeric(ref, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(cur, errors="coerce").dropna().to_numpy()
    n1, n2 = len(a), len(b)
    if n1 < 5 or n2 < 5:
        return {"t": None, "df": None, "p_value": None}
    m1, m2 = float(a.mean()), float(b.mean())
    v1, v2 = float(a.var(ddof=1)), float(b.var(ddof=1))
    se2 = v1 / n1 + v2 / n2
    if se2 <= 0:
        return {"t": 0.0, "df": n1 + n2 - 2, "p_value": 1.0}
    se = math.sqrt(se2)
    t = (m1 - m2) / se
    num = se2 ** 2
    den = (v1 / n1) ** 2 / max(n1 - 1, 1) + (v2 / n2) ** 2 / max(n2 - 1, 1)
    df = num / den if den > 0 else n1 + n2 - 2
    # Normal approximation for t→p (accurate when df > 30)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return {"t": round(t, 4), "df": round(df, 1), "p_value": round(p, 4)}


def compute_cohens_d(ref: pd.Series, cur: pd.Series) -> float | None:
    """Cohen's d effect size (standardized mean difference, pooled SD).

    Interpretation: |d| < 0.2 ⇒ negligible; 0.2–0.5 small; 0.5–0.8 medium; >0.8 large.
    """
    a = pd.to_numeric(ref, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(cur, errors="coerce").dropna().to_numpy()
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    m1, m2 = float(a.mean()), float(b.mean())
    v1, v2 = float(a.var(ddof=1)), float(b.var(ddof=1))
    pooled_var = ((n1 - 1) * v1 + (n2 - 1) * v2) / max(n1 + n2 - 2, 1)
    if pooled_var <= 0:
        return 0.0
    return round((m1 - m2) / math.sqrt(pooled_var), 4)


def compute_js_divergence(ref: pd.Series, cur: pd.Series, bins: int = 20) -> float | None:
    """Jensen-Shannon divergence in bits (log base 2). Bounded [0, 1].

    Smoothed, symmetric variant of KL divergence — robust to zero bins.

    Interpretation: < 0.1 very similar; < 0.2 similar; > 0.5 quite distinct.
    """
    a = pd.to_numeric(ref, errors="coerce").dropna().to_numpy()
    b = pd.to_numeric(cur, errors="coerce").dropna().to_numpy()
    if len(a) < 5 or len(b) < 5:
        return None
    combined = np.concatenate([a, b])
    if combined.size == 0 or np.ptp(combined) == 0:
        return 0.0
    _, edges = np.histogram(combined, bins=bins)
    p, _ = np.histogram(a, bins=edges)
    q, _ = np.histogram(b, bins=edges)
    eps = 1e-12
    p = (p + eps) / (p.sum() + eps * len(p))
    q = (q + eps) / (q.sum() + eps * len(q))
    m = 0.5 * (p + q)
    js = 0.5 * (np.sum(p * np.log2(p / m)) + np.sum(q * np.log2(q / m)))
    return round(max(0.0, min(1.0, float(js))), 4)


def compute_drift(current_df: pd.DataFrame, prior_df, cfg: dict) -> dict:
    """Compute PSI for all configured numeric columns between current and prior quarters."""
    numeric_cols = cfg.get("drift", {}).get("numeric_columns", [])
    bins = cfg.get("drift", {}).get("bins", 5)
    rows = []

    for col in numeric_cols:
        if col not in current_df.columns:
            continue
        cur_series = pd.to_numeric(current_df[col], errors="coerce")
        ref_series = pd.to_numeric(prior_df[col], errors="coerce") if prior_df is not None and col in prior_df.columns else pd.Series([], dtype=float)
        psi = compute_psi(ref_series, cur_series, bins) if prior_df is not None else 0.0
        level = psi_level(psi, cfg)

        # Additional statistical tests — on non-null values only
        ks       = compute_ks_test(ref_series, cur_series)       if prior_df is not None else {"statistic": None, "p_value": None}
        t_test   = compute_welch_t_test(ref_series, cur_series)  if prior_df is not None else {"t": None, "df": None, "p_value": None}
        cohens_d = compute_cohens_d(ref_series, cur_series)      if prior_df is not None else None
        js_div   = compute_js_divergence(ref_series, cur_series, bins=20) if prior_df is not None else None

        rows.append({
            "column": col,
            "psi": psi,
            "level": level,
            "cur_mean": round(float(cur_series.mean()), 4) if not cur_series.empty else None,
            "cur_median": round(float(cur_series.median()), 4) if not cur_series.empty else None,
            "cur_std": round(float(cur_series.std()), 4) if not cur_series.empty else None,
            "cur_missing_pct": round(cur_series.isna().mean() * 100, 2),
            "ref_mean": round(float(ref_series.mean()), 4) if len(ref_series) > 0 else None,
            "ref_median": round(float(ref_series.median()), 4) if len(ref_series) > 0 else None,
            "ref_std": round(float(ref_series.std()), 4) if len(ref_series) > 0 else None,
            "ref_missing_pct": round(ref_series.isna().mean() * 100, 2) if len(ref_series) > 0 else None,
            # New distribution-shift tests (all run on non-null numeric values)
            "ks_stat":  ks.get("statistic"),
            "ks_p":     ks.get("p_value"),
            "anova_p":  t_test.get("p_value"),     # Welch's t-test (2-group ANOVA equivalent)
            "anova_t":  t_test.get("t"),
            "cohens_d": cohens_d,
            "js_div":   js_div,
        })

    rows.sort(key=lambda r: -r["psi"])
    avg_psi = round(float(np.mean([r["psi"] for r in rows])), 4) if rows else 0.0
    max_psi = round(max((r["psi"] for r in rows), default=0.0), 4)
    sig_drift = [r for r in rows if r["psi"] >= cfg.get("drift", {}).get("thresholds", {}).get("moderate", 0.20)]
    high_drift = [r for r in rows if r["level"] == "High"]

    if avg_psi >= 0.25:
        drift_status = "Critical"
    elif avg_psi >= 0.10:
        drift_status = "Elevated"
    else:
        drift_status = "Stable"

    return {
        "columns_analyzed": len(rows),
        "sig_drift_count": len(sig_drift),
        "sig_drift_pct": round(len(sig_drift) / len(rows) * 100, 1) if rows else 0.0,
        "high_drift_count": len(high_drift),
        "avg_psi": avg_psi,
        "max_psi": max_psi,
        "drift_status": drift_status,
        "by_variable": rows,
    }


def compute_population(current_df: pd.DataFrame, prior_df, cfg: dict) -> dict:
    """Compute population movement (new, dropped, continuing accounts) vs prior quarter."""
    id_col = cfg.get("population", {}).get("id_column", "ACCT-SYS-CR-INSMID")
    seg_col = cfg.get("population", {}).get("segment_column", "BUSINESS UNIT")

    cur_ids = set(current_df[id_col].dropna().astype(str))
    prior_ids = set(prior_df[id_col].dropna().astype(str)) if prior_df is not None else set()

    new_ids = cur_ids - prior_ids
    dropped_ids = prior_ids - cur_ids
    continuing_ids = cur_ids & prior_ids

    total = len(cur_ids)
    prior_total = len(prior_ids)

    new_n = len(new_ids)
    dropped_n = len(dropped_ids)
    cont_n = len(continuing_ids)

    new_pct = round(new_n / total * 100, 2) if total > 0 else 0.0
    dropped_pct = round(dropped_n / prior_total * 100, 2) if prior_total > 0 else 0.0
    cont_pct = round(cont_n / total * 100, 2) if total > 0 else 0.0
    net_change = total - prior_total

    # Compute by segment
    segments = sorted(current_df[seg_col].dropna().unique()) if seg_col in current_df.columns else []
    by_segment = []
    for seg in segments:
        cur_seg = set(current_df[current_df[seg_col] == seg][id_col].dropna().astype(str))
        prior_seg = set(prior_df[prior_df[seg_col] == seg][id_col].dropna().astype(str)) if prior_df is not None and seg_col in prior_df.columns else set()
        seg_new = len(cur_seg - prior_seg)
        seg_dropped = len(prior_seg - cur_seg)
        seg_total = len(cur_seg)
        seg_prior_total = len(prior_seg)
        by_segment.append({
            "segment": seg,
            "prior_accounts": seg_prior_total,
            "new_accounts": seg_new,
            "new_pct": round(seg_new / seg_prior_total * 100, 2) if seg_prior_total > 0 else 0.0,
            "dropped_accounts": seg_dropped,
            "dropped_pct": round(seg_dropped / seg_prior_total * 100, 2) if seg_prior_total > 0 else 0.0,
            "current_accounts": seg_total,
            "net_change": seg_total - seg_prior_total,
            "net_change_pct": round((seg_total - seg_prior_total) / seg_prior_total * 100, 2) if seg_prior_total > 0 else 0.0,
        })

    # Estimate PSI for population distribution across segments
    if by_segment and prior_df is not None:
        cur_seg_counts = [s["current_accounts"] for s in by_segment]
        prior_seg_counts = [s["prior_accounts"] for s in by_segment]
        eps = 1e-4
        cur_dist = [(c + eps) / (sum(cur_seg_counts) + eps * len(cur_seg_counts)) for c in cur_seg_counts]
        prior_dist = [(c + eps) / (sum(prior_seg_counts) + eps * len(prior_seg_counts)) for c in prior_seg_counts]
        pop_psi = round(sum((c - p) * np.log(c / p) for c, p in zip(cur_dist, prior_dist)), 4)
        pop_psi = max(0.0, pop_psi)
    else:
        pop_psi = 0.0

    if pop_psi >= 0.2:
        psi_label = "Significant"
    elif pop_psi >= 0.1:
        psi_label = "Moderate"
    else:
        psi_label = "Stable"

    return {
        "total": total,
        "prior_total": prior_total,
        "new": new_n,
        "new_pct": new_pct,
        "dropped": dropped_n,
        "dropped_pct": dropped_pct,
        "continuing": cont_n,
        "continuing_pct": cont_pct,
        "net_change": net_change,
        "net_change_pct": round(net_change / prior_total * 100, 2) if prior_total > 0 else 0.0,
        "psi": pop_psi,
        "psi_label": psi_label,
        "by_segment": by_segment,
    }
