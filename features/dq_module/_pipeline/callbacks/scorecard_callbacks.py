"""Scorecard data builder — port24 vs port25 Q4 comparison rows."""

from __future__ import annotations

import pandas as pd

from ..validation import compute_completeness


def build_scorecard(df25: pd.DataFrame, df24: pd.DataFrame, schema_df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Build port24 vs port25 scorecard for the D8 comparison tab."""

    def _q4(df, year):
        q = f"{year}Q4"
        sub = df[df["_quarter"] == q] if "_quarter" in df.columns else pd.DataFrame()
        return sub

    q25 = _q4(df25, 2025)
    q24 = _q4(df24, 2024)

    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception:
            return None

    def _count(df): return len(df)
    def _balance(df): return round(float(pd.to_numeric(df.get("Balance", pd.Series([], dtype=float)), errors="coerce").sum()) / 1e9, 3) if "Balance" in df.columns else None
    def _comp(df, cfg_):
        c = compute_completeness(df, cfg_)
        return round(c["overall_pct"], 2)
    def _miss_pct(df, col): return round(df[col].isna().mean() * 100, 2) if col in df.columns and not df.empty else None
    def _neg_alll(df): return int((pd.to_numeric(df.get("ALLL", pd.Series([], dtype=float)), errors="coerce") < 0).sum())
    def _cap_zero(df):
        c = "CDW-CAPITAL-CHARGE"
        return int((pd.to_numeric(df.get(c, pd.Series([], dtype=float)), errors="coerce").fillna(0) == 0).sum()) if c in df.columns else None
    def _hvcre(df): return int(((df["HVCRE-FLAG"].astype(str) == "Y") & (df["BASELII-CATEGORY"].astype(str) != "CRE")).sum()) if "HVCRE-FLAG" in df.columns and "BASELII-CATEGORY" in df.columns else None
    def _lgd_gap(df):
        m = pd.to_numeric(df.get("MODEL LGD", pd.Series([], dtype=float)), errors="coerce")
        a = pd.to_numeric(df.get("LOSS-GVN-DFLT-FAC", pd.Series([], dtype=float)), errors="coerce")
        gap = (m - a).dropna()
        return round(float(gap.mean()), 4) if not gap.empty else None
    def _sme_xbu(df): return int(((df["SME-IND"].astype(str) == "Y") & (df["BUSINESS UNIT"].astype(str) != "SME")).sum()) if "SME-IND" in df.columns and "BUSINESS UNIT" in df.columns else None
    def _manual(df): return int((df["Balance Source"].astype(str) == "MANUAL").sum()) if "Balance Source" in df.columns else None

    def _rag(v24, v25, threshold, lower_is_better=False):
        if v24 is None or v25 is None:
            return "GRAY"
        delta = v25 - v24
        if lower_is_better:
            return "RED" if delta > threshold else ("AMBER" if delta > 0 else "GREEN")
        else:
            return "RED" if delta < -threshold else ("AMBER" if delta < 0 else "GREEN")

    v24_rec = _safe(_count, q24);   v25_rec = _safe(_count, q25)
    v24_bal = _safe(_balance, q24); v25_bal = _safe(_balance, q25)
    v24_comp = _safe(_comp, q24, cfg); v25_comp = _safe(_comp, q25, cfg)
    v24_dscr = _safe(_miss_pct, q24, "DSCR"); v25_dscr = _safe(_miss_pct, q25, "DSCR")
    v24_alll = _safe(_neg_alll, q24); v25_alll = _safe(_neg_alll, q25)
    v24_cap = _safe(_cap_zero, q24);  v25_cap = _safe(_cap_zero, q25)
    v24_hvcre = _safe(_hvcre, q24);   v25_hvcre = _safe(_hvcre, q25)
    v24_lgd = _safe(_lgd_gap, q24);   v25_lgd = _safe(_lgd_gap, q25)
    v24_sme = _safe(_sme_xbu, q24);   v25_sme = _safe(_sme_xbu, q25)
    v24_man = _safe(_manual, q24);    v25_man = _safe(_manual, q25)

    def _fmt_delta(v24, v25, unit=""):
        if v24 is None or v25 is None:
            return "—"
        d = v25 - v24
        return f"{d:+.3f}{unit}" if isinstance(d, float) else f"{d:+d}{unit}"

    rows = [
        {"metric": "Total Record Count", "field": "ACCT-SYS-CR-INSMID", "v24": v24_rec, "v25": v25_rec, "delta": _fmt_delta(v24_rec, v25_rec), "rag": _rag(v24_rec, v25_rec, 0, False), "red_flag": "port25 < port24", "dashboard": "D1, D6"},
        {"metric": "Total Balance (USD Bn)", "field": "Balance", "v24": v24_bal, "v25": v25_bal, "delta": _fmt_delta(v24_bal, v25_bal, " Bn"), "rag": "RED" if (v24_bal and v25_bal and abs(v25_bal - v24_bal) / max(abs(v24_bal), 0.001) > 0.01) else "GREEN", "red_flag": ">1% gap vs port24", "dashboard": "D1"},
        {"metric": "Overall Completeness %", "field": "All 116 cols", "v24": v24_comp, "v25": v25_comp, "delta": _fmt_delta(v24_comp, v25_comp, "pp"), "rag": _rag(v24_comp, v25_comp, 0.5, False), "red_flag": "port25 < port24 by >0.5pp", "dashboard": "D4"},
        {"metric": "DSCR Missing % (CRE)", "field": "DSCR", "v24": v24_dscr, "v25": v25_dscr, "delta": _fmt_delta(v24_dscr, v25_dscr, "pp"), "rag": _rag(v24_dscr, v25_dscr, 1.0, True), "red_flag": "port25 > port24 by >1pp", "dashboard": "D1, D4"},
        {"metric": "Negative ALLL Record Count", "field": "ALLL", "v24": v24_alll, "v25": v25_alll, "delta": _fmt_delta(v24_alll, v25_alll), "rag": _rag(v24_alll, v25_alll, 0, True) if v24_alll is not None and v25_alll is not None else "GRAY", "red_flag": "port25 > port24 count", "dashboard": "D1, D4, D5"},
        {"metric": "CDW-CAPITAL-CHARGE All-Zero Count", "field": "CDW-CAPITAL-CHARGE", "v24": v24_cap, "v25": v25_cap, "delta": _fmt_delta(v24_cap, v25_cap) if v24_cap is not None else "—", "rag": "RED" if (v25_cap is not None and v25_cap > 0 and (v24_cap is None or v24_cap == 0)) else ("GREEN" if v25_cap == 0 else "GRAY"), "red_flag": "port25 all-zero, port24 not", "dashboard": "D1, D5"},
        {"metric": "HVCRE/BASELII-CATEGORY Mismatch", "field": "HVCRE-FLAG, BASELII-CATEGORY", "v24": v24_hvcre, "v25": v25_hvcre, "delta": _fmt_delta(v24_hvcre, v25_hvcre), "rag": _rag(v24_hvcre, v25_hvcre, 0, True), "red_flag": "port25 > port24", "dashboard": "D1, D5"},
        {"metric": "MODEL LGD vs Applied LGD Gap (pp)", "field": "MODEL LGD, LOSS-GVN-DFLT-FAC", "v24": v24_lgd, "v25": v25_lgd, "delta": _fmt_delta(v24_lgd, v25_lgd, "pp"), "rag": _rag(v24_lgd, v25_lgd, 0.05, True) if v24_lgd is not None and v25_lgd is not None else "GRAY", "red_flag": "gap widened by >5pp", "dashboard": "D2, D5, D7"},
        {"metric": "SME-IND=Y Outside SME BU", "field": "SME-IND, BUSINESS UNIT", "v24": v24_sme, "v25": v25_sme, "delta": _fmt_delta(v24_sme, v25_sme), "rag": _rag(v24_sme, v25_sme, 10, True), "red_flag": "port25 > port24 by >10", "dashboard": "D5, D6"},
        {"metric": "MANUAL Balance Source Count", "field": "Balance Source", "v24": v24_man, "v25": v25_man, "delta": _fmt_delta(v24_man, v25_man), "rag": _rag(v24_man, v25_man, 0, True), "red_flag": "port25 > port24", "dashboard": "D1, D2"},
    ]
    return rows
