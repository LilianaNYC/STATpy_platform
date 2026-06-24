"""Segment-by-dimension breakdowns used by the Completeness + Summary Details tabs.

`completeness_by_dim` — per dimension value: account count, completeness %,
missing %, and the change vs a prior snapshot. Drives the "Additional
Segmentations" cards at the bottom of the Completeness page.

`balance_by_dim` — per dimension value: records, current balance, prior
balance, and balance ratio %. Drives the Summary Details page tables,
modelled after the user's CCAR-style "Balance Check" Excel sheet.

Both helpers:
  - Treat NaN as a literal 'NULL' bucket (matching the screenshots).
  - Sort segment labels alphabetically for stable display.
  - Skip dimensions that aren't present in the supplied dataframe.
"""

from __future__ import annotations

import pandas as pd


# Dimensions surfaced on the Summary Details page (8) and the Completeness
# page (7 — Business Unit is omitted because the existing "By Business
# Segment" card already covers it). Order matches the screenshots.
SEGMENT_DIMS = [
    {"key": "business_unit",     "label": "Business Unit",             "column": "BUSINESS UNIT"},
    {"key": "model_14a_line",    "label": "Model 14A Line",            "column": "MODEL-14A-LINE"},
    {"key": "facility_type",     "label": "Facility Type Description", "column": "FACILITY TYPE DESCRIPTION"},
    {"key": "scr_code",          "label": "SCR Code",                  "column": "SCR-CDE-1"},
    {"key": "blackrock_bus_fcl", "label": "Blackrock Bus FCL",         "column": "BLACKROCK-BUS-FCL"},
    {"key": "committed_ind",     "label": "Committed Ind",             "column": "COMMITTED-IND"},
    {"key": "direct_contingent", "label": "Direct / Contingent",       "column": "DIRECT/CONTINGENT IND"},
    {"key": "rwa_calc_flag",     "label": "RWA Calc Flag",             "column": "RWA-CALC-FLAG"},
]

# Dimensions to add to the Completeness page (skip Business Unit — already shown there)
COMPLETENESS_EXTRA_DIMS = [d for d in SEGMENT_DIMS if d["key"] != "business_unit"]


def _completeness_pct(df: pd.DataFrame, measure_cols: list[str]) -> float | None:
    """Completeness % over the supplied measure columns. None if the slice is empty."""
    if df is None or df.empty or not measure_cols:
        return None
    cols = [c for c in measure_cols if c in df.columns]
    if not cols:
        return None
    sub = df[cols]
    n_vals = sub.size
    if n_vals == 0:
        return None
    n_missing = int(sub.isna().sum().sum())
    return round((1 - n_missing / n_vals) * 100, 2)


def completeness_by_dim(df_current: pd.DataFrame,
                        df_prior: pd.DataFrame | None,
                        dim_col: str,
                        measure_cols: list[str]) -> list[dict]:
    """Per dimension value: accounts, completeness %, missing %, Δ vs prior.

    `measure_cols` is typically the schema-flagged key variables — completeness is
    computed against just those columns to keep the metric focused on the variables
    the team actually cares about.
    """
    if dim_col not in df_current.columns:
        return []
    df_cur = df_current.copy()
    df_cur[dim_col] = df_cur[dim_col].fillna("NULL").astype(str)
    df_prv: pd.DataFrame | None = None
    if df_prior is not None and dim_col in df_prior.columns:
        df_prv = df_prior.copy()
        df_prv[dim_col] = df_prv[dim_col].fillna("NULL").astype(str)

    rows: list[dict] = []
    for seg in sorted(df_cur[dim_col].unique()):
        sub = df_cur[df_cur[dim_col] == seg]
        if sub.empty:
            continue
        comp = _completeness_pct(sub, measure_cols)
        if comp is None:
            continue
        missing = round(100 - comp, 2)

        comp_prior: float | None = None
        if df_prv is not None:
            sub_prv = df_prv[df_prv[dim_col] == seg]
            if not sub_prv.empty:
                comp_prior = _completeness_pct(sub_prv, measure_cols)
        delta = round(comp - comp_prior, 2) if comp_prior is not None else None

        rows.append({
            "segment": seg,
            "accounts": int(len(sub)),
            "completeness_pct": comp,
            "missing_pct": missing,
            "comp_prior_pct": comp_prior,
            "comp_delta": delta,
        })
    return rows


def balance_by_dim(df_current: pd.DataFrame,
                   df_prior: pd.DataFrame | None,
                   dim_col: str,
                   balance_col: str = "Balance") -> list[dict]:
    """Per dimension value: records, current_balance, prior_balance, ratio %.

    Matches the CCAR "Balance Check" sheet shape from the user's screenshots.
    Ratio % = current / prior * 100. None if the prior balance is zero.
    """
    if dim_col not in df_current.columns or balance_col not in df_current.columns:
        return []
    df_cur = df_current.copy()
    df_cur[dim_col] = df_cur[dim_col].fillna("NULL").astype(str)
    df_prv: pd.DataFrame | None = None
    if df_prior is not None and dim_col in df_prior.columns and balance_col in df_prior.columns:
        df_prv = df_prior.copy()
        df_prv[dim_col] = df_prv[dim_col].fillna("NULL").astype(str)

    cur_balance = df_cur.groupby(dim_col, dropna=False)[balance_col].sum()
    cur_count = df_cur.groupby(dim_col, dropna=False).size()
    prv_balance = (
        df_prv.groupby(dim_col, dropna=False)[balance_col].sum()
        if df_prv is not None else pd.Series(dtype=float)
    )
    prv_count = (
        df_prv.groupby(dim_col, dropna=False).size()
        if df_prv is not None else pd.Series(dtype=int)
    )

    segs = sorted(set(cur_balance.index) | set(prv_balance.index))
    rows: list[dict] = []
    for seg in segs:
        c_bal = float(cur_balance.get(seg, 0.0))
        p_bal = float(prv_balance.get(seg, 0.0))
        c_rec = int(cur_count.get(seg, 0))
        p_rec = int(prv_count.get(seg, 0))
        bal_ratio = round((c_bal / p_bal) * 100, 1) if abs(p_bal) > 1e-9 else None
        rec_ratio = round((c_rec / p_rec) * 100, 1) if p_rec > 0 else None
        rows.append({
            "segment": str(seg),
            "records": c_rec,                     # current count
            "prior_records": p_rec,               # prior count
            "record_change": c_rec - p_rec,
            "record_ratio_pct": rec_ratio,
            "current_balance": round(c_bal, 2),
            "prior_balance": round(p_bal, 2),
            "ratio_pct": bal_ratio,
        })
    return rows


def detect_count_anomalies(summary_segments: dict[str, dict],
                           ratio_threshold: float = 2.0,
                           abs_min: int = 10) -> list[dict]:
    """Flag segments with drastic record-count swings between the two periods.

    Four kinds:
      - 'appeared'        — prior == 0, current > 0 (new segment)
      - 'disappeared'     — prior > 0, current == 0 (segment dropped out)
      - 'drastic_growth'  — current/prior >= ratio_threshold AND change >= abs_min
      - 'drastic_drop'    — current/prior <= 1/ratio_threshold AND |change| >= abs_min
    """
    alerts: list[dict] = []
    for dim_key, entry in summary_segments.items():
        for row in entry.get("rows", []):
            p = int(row.get("prior_records", 0) or 0)
            c = int(row.get("records", 0) or 0)
            base = {
                "dim_key": dim_key,
                "dim_label": entry.get("label", dim_key),
                "dim_column": entry.get("column", ""),
                "segment": row["segment"],
                "prior": p,
                "current": c,
                "change": c - p,
            }
            if p == 0 and c > 0:
                alerts.append({**base, "kind": "appeared",
                               "severity": "high" if c >= abs_min else "low"})
            elif p > 0 and c == 0:
                alerts.append({**base, "kind": "disappeared",
                               "severity": "high" if p >= abs_min else "low"})
            elif p > 0 and c > 0:
                r = c / p
                if r >= ratio_threshold and (c - p) >= abs_min:
                    alerts.append({**base, "kind": "drastic_growth", "severity": "high"})
                elif r <= (1.0 / ratio_threshold) and (p - c) >= abs_min:
                    alerts.append({**base, "kind": "drastic_drop", "severity": "high"})
    # Sort by abs(change) descending so the biggest swings come first.
    alerts.sort(key=lambda a: -abs(a["change"]))
    return alerts
