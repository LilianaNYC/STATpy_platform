"""Population page data builders — migration matrix + filter slices."""

from __future__ import annotations

import pandas as pd


# ── Filter dimensions surfaced in the Population tab ───────────
# Each dimension drives one dropdown on the page. Add/remove here to extend.
FILTER_DIMENSIONS = {
    "by_bu":     {"label": "Business Unit",      "column": "BUSINESS UNIT"},
    "by_basel":  {"label": "Basel II Category",  "column": "BASELII-CATEGORY"},
    "by_rating": {"label": "Risk Rating",        "column": "FNL-CUST-RISK-GR"},
}

RATING_BUCKETS = ["IG (1-4)", "Sub-IG (5-7)", "Distressed (8-9)"]


def _rating_bucket(val):
    """Map a granular rating (e.g. 3.1) to one of three regulatory buckets."""
    if val is None or pd.isna(val):
        return None
    try:
        first = int(float(val))
    except Exception:
        return None
    if 1 <= first <= 4: return "IG (1-4)"
    if 5 <= first <= 7: return "Sub-IG (5-7)"
    if 8 <= first <= 9: return "Distressed (8-9)"
    return None


def _slim_pop(cur_ids: set, prior_ids: set) -> dict:
    """Lightweight population metrics from already-resolved ID sets."""
    total = len(cur_ids)
    prior = len(prior_ids)
    new = len(cur_ids - prior_ids)
    dropped = len(prior_ids - cur_ids)
    cont = len(cur_ids & prior_ids)
    return {
        "total": total, "prior_total": prior,
        "new": new, "dropped": dropped, "continuing": cont,
        "new_pct":        round(new     / total * 100, 2) if total else 0.0,
        "dropped_pct":    round(dropped / prior * 100, 2) if prior else 0.0,
        "continuing_pct": round(cont    / total * 100, 2) if total else 0.0,
        "net_change":     total - prior,
        "net_change_pct": round((total - prior) / prior * 100, 2) if prior else 0.0,
    }


def _ids_by_value(df: pd.DataFrame, col: str, id_col: str, value, bucket_fn=None) -> set:
    """Return ID set for rows where df[col] matches `value` (optionally via a bucket fn)."""
    if col not in df.columns or id_col not in df.columns or df.empty:
        return set()
    if bucket_fn is None:
        mask = df[col].astype(str) == str(value)
    else:
        mask = df[col].apply(bucket_fn) == value
    return set(df.loc[mask, id_col].dropna().astype(str))


def discover_filter_values(df: pd.DataFrame) -> dict:
    """Enumerate the distinct values per filter dimension across the full dataset."""
    out = {}
    bu_col   = FILTER_DIMENSIONS["by_bu"]["column"]
    basel_col= FILTER_DIMENSIONS["by_basel"]["column"]
    rating_col=FILTER_DIMENSIONS["by_rating"]["column"]

    out["by_bu"]     = sorted(df[bu_col].dropna().astype(str).unique())     if bu_col    in df.columns else []
    out["by_basel"]  = sorted(df[basel_col].dropna().astype(str).unique())  if basel_col in df.columns else []
    out["by_rating"] = [b for b in RATING_BUCKETS if b in df[rating_col].apply(_rating_bucket).dropna().unique()] if rating_col in df.columns else []
    return out


def build_filter_slices(cur_df: pd.DataFrame, prior_df, cfg: dict,
                        values: dict) -> dict:
    """For one quarter, return slim pop metrics per (dimension, value)."""
    id_col = cfg.get("population", {}).get("id_column", "ACCT-SYS-CR-INSMID")
    slices = {"by_bu": {}, "by_basel": {}, "by_rating": {}}

    bu_col    = FILTER_DIMENSIONS["by_bu"]["column"]
    basel_col = FILTER_DIMENSIONS["by_basel"]["column"]
    rating_col= FILTER_DIMENSIONS["by_rating"]["column"]

    for v in values.get("by_bu", []):
        cur_ids = _ids_by_value(cur_df, bu_col, id_col, v)
        prv_ids = _ids_by_value(prior_df, bu_col, id_col, v) if prior_df is not None else set()
        slices["by_bu"][v] = _slim_pop(cur_ids, prv_ids)

    for v in values.get("by_basel", []):
        cur_ids = _ids_by_value(cur_df, basel_col, id_col, v)
        prv_ids = _ids_by_value(prior_df, basel_col, id_col, v) if prior_df is not None else set()
        slices["by_basel"][v] = _slim_pop(cur_ids, prv_ids)

    for v in values.get("by_rating", []):
        cur_ids = _ids_by_value(cur_df, rating_col, id_col, v, bucket_fn=_rating_bucket)
        prv_ids = _ids_by_value(prior_df, rating_col, id_col, v, bucket_fn=_rating_bucket) if prior_df is not None else set()
        slices["by_rating"][v] = _slim_pop(cur_ids, prv_ids)

    return slices


# ── Implied PD lookup by rating grade (industry-typical mapping) ───────
_IMP_PD_BY_RATING = {
    "1.1": 0.0003, "1.2": 0.0005,
    "2.1": 0.0010, "2.2": 0.0020,
    "3.1": 0.0035, "3.2": 0.0060,
    "4.1": 0.0100, "4.2": 0.0180,
    "5.1": 0.0300, "5.2": 0.0500,
    "6.1": 0.0800, "6.2": 0.1200,
    "7.1": 0.1700, "7.2": 0.2300,
    "8.1": 0.4000, "9.0": 1.0000,
}


def _imp_pd(rating) -> float:
    if rating is None or pd.isna(rating):
        return None
    key = str(rating)
    if key in _IMP_PD_BY_RATING:
        return _IMP_PD_BY_RATING[key]
    # Try numeric match (e.g., "1.1" vs 1.1)
    try:
        for k, v in _IMP_PD_BY_RATING.items():
            if abs(float(k) - float(rating)) < 0.01:
                return v
    except Exception:
        pass
    return None


def build_crr_analysis(cur_df: pd.DataFrame, prior_df, cfg: dict) -> dict | None:
    """CRR migration analysis for retained facilities between PQ and CQ.

    Returns counts/balance deltas per CRR grade (upgrades vs downgrades)
    plus aggregate summary tables shown on the right side of the chart.
    """
    if prior_df is None or prior_df.empty:
        return None

    fcl_col = cfg["data"].get("facility_id_column", "FCL-ID")
    crr_col = "FNL-CUST-RISK-GR"
    bal_col = "Balance"

    required = [fcl_col, crr_col, bal_col]
    if not all(c in cur_df.columns for c in required) or not all(c in prior_df.columns for c in required):
        return None

    def _per_fcl(df: pd.DataFrame) -> pd.DataFrame:
        # Take the row with max balance per facility as the representative CRR
        df = df.dropna(subset=[fcl_col]).copy()
        df[bal_col] = pd.to_numeric(df[bal_col], errors="coerce").fillna(0)
        idx = df.groupby(fcl_col)[bal_col].idxmax()
        rep = df.loc[idx, [fcl_col, crr_col, bal_col]].rename(
            columns={crr_col: "crr", bal_col: "balance"}
        )
        # Aggregate total balance per facility (sum across all rows)
        bal_sum = df.groupby(fcl_col)[bal_col].sum().rename("balance_sum").reset_index()
        rep = rep.drop(columns=["balance"]).merge(bal_sum, on=fcl_col)
        rep = rep.rename(columns={"balance_sum": "balance"})
        return rep

    cur_rep = _per_fcl(cur_df)
    prv_rep = _per_fcl(prior_df)

    # Retained = FCLs present in both quarters
    merged = cur_rep.merge(prv_rep, on=fcl_col, suffixes=("_cur", "_prv"), how="inner")
    if merged.empty:
        return {
            "retained_summary": {"upgrades_count": 0, "downgrades_count": 0, "net_count": 0,
                                  "upgrades_balance": 0, "downgrades_balance": 0, "net_balance": 0},
            "by_crr": [],
            "retained_metrics": {"prior_avg_crr": None, "current_avg_crr": None,
                                  "prior_imp_pd": None, "current_imp_pd": None},
            "retained_count": 0,
        }

    cur_n = pd.to_numeric(merged["crr_cur"], errors="coerce")
    prv_n = pd.to_numeric(merged["crr_prv"], errors="coerce")
    merged["delta"] = cur_n - prv_n
    merged["is_upgrade"]   = merged["delta"] < 0   # lower CRR = better grade
    merged["is_downgrade"] = merged["delta"] > 0
    merged["bal_change"]   = merged["balance_cur"] - merged["balance_prv"]

    # Per CRR grade (bucket by CURRENT CRR — i.e. where the customer landed)
    grades = sorted(
        set(merged["crr_cur"].dropna().astype(str).unique()),
        key=lambda x: float(x) if x.replace(".","").isdigit() else 99,
    )
    by_crr = []
    for g in grades:
        sub = merged[merged["crr_cur"].astype(str) == g]
        up   = int(sub["is_upgrade"].sum())
        down = int(sub["is_downgrade"].sum())
        by_crr.append({
            "crr": g,
            "upgrades":   up,
            "downgrades": -down,   # negative for plotting below zero
            "net":        up - down,
            "balance_change": round(float(sub["bal_change"].sum()) / 1e6, 2),  # millions
        })

    # Aggregate balance flows in millions
    up_bal   = round(float(merged.loc[merged["is_upgrade"],   "bal_change"].sum()) / 1e6, 2)
    down_bal = round(float(merged.loc[merged["is_downgrade"], "bal_change"].sum()) / 1e6, 2)
    n_up   = int(merged["is_upgrade"].sum())
    n_down = int(merged["is_downgrade"].sum())

    # Weighted-by-balance Avg CRR + Implied PD per side
    def _avg(crr_series: pd.Series, bal_series: pd.Series) -> float | None:
        v = pd.to_numeric(crr_series, errors="coerce")
        b = pd.to_numeric(bal_series, errors="coerce").fillna(0)
        mask = v.notna() & (b > 0)
        if not mask.any():
            return None
        return round(float((v[mask] * b[mask]).sum() / b[mask].sum()), 2)

    def _avg_pd(crr_series: pd.Series, bal_series: pd.Series) -> float | None:
        pds = crr_series.apply(_imp_pd)
        b = pd.to_numeric(bal_series, errors="coerce").fillna(0)
        mask = pds.notna() & (b > 0)
        if not mask.any():
            return None
        return round(float((pds[mask] * b[mask]).sum() / b[mask].sum()) * 100, 2)  # pct

    # ── CRR Migration Matrix (from_crr → to_crr) ───────────────────
    def _grade_key(g):
        try: return float(g)
        except Exception: return 99.0

    all_grades_set: set = set()
    for g in merged["crr_prv"].dropna(): all_grades_set.add(str(g))
    for g in merged["crr_cur"].dropna(): all_grades_set.add(str(g))
    all_grades_list = sorted(all_grades_set, key=_grade_key)

    matrix_crr = {g_from: {g_to: {"count": 0, "balance": 0.0} for g_to in all_grades_list}
                  for g_from in all_grades_list}
    for _, row in merged.iterrows():
        g_from = str(row["crr_prv"]) if pd.notna(row["crr_prv"]) else None
        g_to   = str(row["crr_cur"]) if pd.notna(row["crr_cur"]) else None
        if g_from in matrix_crr and g_to in matrix_crr.get(g_from, {}):
            matrix_crr[g_from][g_to]["count"] += 1
            matrix_crr[g_from][g_to]["balance"] += float(row.get("bal_change", 0.0))

    # Round balance to $M
    for g_from in matrix_crr:
        for g_to in matrix_crr[g_from]:
            matrix_crr[g_from][g_to]["balance"] = round(matrix_crr[g_from][g_to]["balance"] / 1e6, 2)

    return {
        "retained_count": len(merged),
        "retained_summary": {
            "upgrades_count":   n_up,
            "downgrades_count": n_down,
            "net_count":        n_up - n_down,
            "upgrades_balance":   up_bal,
            "downgrades_balance": down_bal,
            "net_balance":        round(up_bal + down_bal, 2),
        },
        "by_crr": by_crr,
        "retained_metrics": {
            "prior_avg_crr":   _avg(merged["crr_prv"], merged["balance_prv"]),
            "current_avg_crr": _avg(merged["crr_cur"], merged["balance_cur"]),
            "prior_imp_pd":    _avg_pd(merged["crr_prv"], merged["balance_prv"]),
            "current_imp_pd":  _avg_pd(merged["crr_cur"], merged["balance_cur"]),
        },
        "crr_migration_matrix": {
            "grades": all_grades_list,
            "matrix": matrix_crr,
        },
    }


def build_migration_matrix(current_df: pd.DataFrame, prior_df: pd.DataFrame | None,
                           seg_col: str, id_col: str) -> dict:
    """Compute segment migration matrix from prior to current quarter."""
    if prior_df is None or seg_col not in current_df.columns or id_col not in current_df.columns:
        return {}
    segments = sorted(set(current_df[seg_col].dropna().unique()) | set(prior_df[seg_col].dropna().unique()))
    cur_map = current_df.set_index(id_col)[seg_col].to_dict() if id_col in current_df.columns else {}
    prior_map = prior_df.set_index(id_col)[seg_col].to_dict() if id_col in prior_df.columns else {}
    matrix: dict[str, dict[str, int]] = {s: {t: 0 for t in segments + ["Dropped"]} for s in segments}
    for acc_id, prior_seg in prior_map.items():
        if pd.isna(prior_seg):
            continue
        prior_seg = str(prior_seg)
        if prior_seg not in matrix:
            continue
        if str(acc_id) in cur_map:
            cur_seg = str(cur_map[str(acc_id)])
            if cur_seg in matrix[prior_seg]:
                matrix[prior_seg][cur_seg] += 1
            else:
                matrix[prior_seg]["Dropped"] += 1
        else:
            matrix[prior_seg]["Dropped"] += 1
    return {"segments": segments, "matrix": matrix}
