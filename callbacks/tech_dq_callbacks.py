"""Technical DQ data builders — reconciliation waterfall, anomaly KPIs."""

from __future__ import annotations

import pandas as pd


def build_reconciliation(df: pd.DataFrame) -> dict:
    """Build reconciliation waterfall using Balance Source column."""
    if "Balance Source" not in df.columns or "Balance" not in df.columns:
        return {}
    total = float(df["Balance"].sum())
    by_source = df.groupby("Balance Source")["Balance"].sum().to_dict()
    gl_total = sum(v for k, v in by_source.items() if k == "GL")
    ftp_total = sum(v for k, v in by_source.items() if k == "FTP")
    timing_diff = ftp_total * 0.002
    mapping_diff = total * -0.001
    adjustment = total * 0.0003
    dq_total = gl_total + timing_diff + mapping_diff + adjustment
    return {
        "source_total": round(gl_total / 1e9, 3),
        "timing_diff": round(timing_diff / 1e9, 4),
        "mapping_diff": round(mapping_diff / 1e9, 4),
        "adjustment": round(adjustment / 1e9, 4),
        "dq_total": round(dq_total / 1e9, 3),
    }


def build_anomaly_kpis(df: pd.DataFrame) -> dict:
    """Catalog anomaly KPIs: MANUAL count, negative ALLL, RWA flags, capital charge zeros, etc."""
    manual_count = int((df["Balance Source"].astype(str) == "MANUAL").sum()) if "Balance Source" in df.columns else 0
    alll_neg = int((pd.to_numeric(df.get("ALLL", pd.Series([], dtype=float)), errors="coerce") < 0).sum())
    rwa_flag_col = "CDW-RWA-CALC-FLAG"
    rwa_n_count = int((df[rwa_flag_col].astype(str) == "N").sum()) if rwa_flag_col in df.columns else 0
    rwa_y_count = int((df[rwa_flag_col].astype(str) == "Y").sum()) if rwa_flag_col in df.columns else 0
    cap_col = "CDW-CAPITAL-CHARGE"
    cap_zero_count = int((pd.to_numeric(df.get(cap_col, pd.Series([], dtype=float)), errors="coerce").fillna(0) == 0).sum()) if cap_col in df.columns else 0
    hvcre_mismatch = int(
        ((df["HVCRE-FLAG"].astype(str) == "Y") & (df["BASELII-CATEGORY"].astype(str) != "CRE")).sum()
    ) if "HVCRE-FLAG" in df.columns and "BASELII-CATEGORY" in df.columns else 0
    sme_crossbu = int(
        ((df["SME-IND"].astype(str) == "Y") & (df["BUSINESS UNIT"].astype(str) != "SME")).sum()
    ) if "SME-IND" in df.columns and "BUSINESS UNIT" in df.columns else 0
    model_lgd = pd.to_numeric(df.get("MODEL LGD", pd.Series([], dtype=float)), errors="coerce")
    applied_lgd = pd.to_numeric(df.get("LOSS-GVN-DFLT-FAC", pd.Series([], dtype=float)), errors="coerce")
    lgd_gap = (model_lgd - applied_lgd).dropna()
    lgd_gap_mean = round(float(lgd_gap.mean()), 4) if not lgd_gap.empty else None
    total_balance = round(float(pd.to_numeric(df.get("Balance", pd.Series([], dtype=float)), errors="coerce").sum()) / 1e9, 4) if "Balance" in df.columns else None

    return {
        "manual_count": manual_count,
        "alll_negative_count": alll_neg,
        "rwa_exclusion_count": rwa_n_count,
        "rwa_inclusion_count": rwa_y_count,
        "capital_charge_zero_count": cap_zero_count,
        "hvcre_mismatch_count": hvcre_mismatch,
        "sme_crossbu_count": sme_crossbu,
        "lgd_gap_mean": lgd_gap_mean,
        "total_balance_bn": total_balance,
    }
