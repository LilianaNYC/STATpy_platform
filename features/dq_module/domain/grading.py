"""Pure DQ grading rules — framework-agnostic (no Dash, no I/O).

Three rule families, extracted so the business thresholds live in exactly one
place; ``ui/common.py`` imports them back and decorates with presentation
concerns (number formatters, glyphs, colors):

  - missing-data severity (the canonical 4-bucket rule + its label/range text),
  - drift stat-test levels (`TEST_META_BASE` + `verdict_for`),
  - segment count-anomaly detection (`detect_count_anomalies`).
"""

from __future__ import annotations


# ── Missing-data severity — canonical 4 buckets at 0 / ≤1% / ≤10% / >10% ──
# Single source of truth for every Completeness severity widget (donut, table,
# filter, variable-table column, migration matrix, KPI row). >25% folds into
# High by design — the exact % is always visible in the variable table.
MISSING_BUCKETS = ["No Missings", "Low", "Medium", "High"]
MISSING_BUCKET_COLORS = {  # pale backgrounds (table cells / matrix headers)
    "No Missings": "#dcfce7", "Low": "#bbf7d0", "Medium": "#fef3c7",
    "High": "#fee2e2",
}
MISSING_BUCKET_TONES = {  # vivid foreground (donut slices, KPI accents, badges)
    "No Missings": "#16a34a", "Low": "#65a30d", "Medium": "#d97706",
    "High": "#dc2626",
}
MISSING_BUCKET_RANGES = {
    "No Missings": "0% (no nulls)", "Low": "0% < missing ≤ 1%",
    "Medium": "1% < missing ≤ 10%", "High": "> 10%",
}
MISSING_BUCKET_NOTE = ("Severity (by missing %): High > 10%, Medium 1–10%, "
                       "Low ≤ 1%, No Missings 0%")
SEV_NOTE = ("Severity thresholds: Critical >25%, High >10%, Medium >5%, "
            "Low >1% missing")


def missing_bucket(missing_pct) -> str:
    v = 0.0 if missing_pct is None else float(missing_pct)
    if v <= 0:
        return "No Missings"
    if v <= 1:
        return "Low"
    if v <= 10:
        return "Medium"
    return "High"


# ── Drift stat-test levels + verdict ─────────────────────────────────────
# Each _lvl_* grades one statistic into red/amber/green/none. TEST_META_BASE
# carries the static metadata (key/label/short/buckets/help + the level fn);
# the UI layer adds the per-test number formatter. verdict_for() rolls the
# per-test levels into one drift verdict for a variable.

def _lvl_psi(v):
    return "none" if v is None else ("red" if v > 0.20 else "amber" if v > 0.10 else "green")


def _lvl_p(v):
    return "none" if v is None else ("red" if v < 0.01 else "amber" if v < 0.05 else "green")


def _lvl_cohen(v):
    if v is None:
        return "none"
    a = abs(v)
    return "red" if a > 0.5 else "amber" if a > 0.2 else "green"


def _lvl_js(v):
    return "none" if v is None else ("red" if v > 0.5 else "amber" if v > 0.2 else "green")


TEST_META_BASE = [
    {"key": "psi", "label": "PSI", "short": "PSI",
     "level": _lvl_psi, "buckets": ["≤0.10", "0.10–0.20", ">0.20"],
     "help": ("Population Stability Index — compares the binned distribution of "
              "a variable now vs the reference period. Rule of thumb: ≤0.10 "
              "stable · 0.10–0.20 moderate shift · >0.20 significant shift.")},
    {"key": "ks_p", "label": "KS p-value", "short": "KS",
     "level": _lvl_p, "buckets": ["p ≥ 0.05", "p 0.01–0.05", "p < 0.01"],
     "help": ("Kolmogorov–Smirnov p-value — probability the two periods' "
              "distributions are the same. Low p means a real shift: p<0.01 "
              "strong evidence of drift · p≥0.05 no significant change.")},
    {"key": "anova_p", "label": "ANOVA p-value", "short": "ANOVA",
     "level": _lvl_p, "buckets": ["p ≥ 0.05", "p 0.01–0.05", "p < 0.01"],
     "help": ("Analysis-of-variance p-value on the group means — tests whether "
              "the variable's mean differs between the two periods. p<0.01 "
              "flags a significant mean shift · p≥0.05 no significant "
              "difference.")},
    {"key": "cohens_d", "label": "Cohen's d", "short": "Cohen",
     "level": _lvl_cohen, "buckets": ["|d| ≤ 0.2", "0.2–0.5", "> 0.5"],
     "help": ("Cohen's d — standardized difference between the two periods' "
              "means (in standard deviations). |d|≤0.2 negligible · 0.2–0.5 "
              "small/moderate · >0.5 large. Sign shows the direction.")},
    {"key": "js_div", "label": "JS Divergence", "short": "JS",
     "level": _lvl_js, "buckets": ["≤ 0.2", "0.2–0.5", "> 0.5"],
     "help": ("Jensen–Shannon divergence — a 0–1 distance between the two "
              "distributions (0 = identical). ≤0.2 minor · 0.2–0.5 moderate · "
              ">0.5 large divergence.")},
]


def verdict_for(row) -> dict:
    """3+ red tests → Drift · 1–2 red → Mixed · else Stable."""
    red = sum(1 for t in TEST_META_BASE if t["level"](row.get(t["key"])) == "red")
    level = "red" if red >= 3 else "amber" if red >= 1 else "green"
    label = "⚠ Drift" if red >= 3 else "◐ Mixed" if red >= 1 else "✓ Stable"
    return {"level": level, "label": label, "red_count": red}


# ── Segment count-anomaly detection ──────────────────────────────────────

def detect_count_anomalies(summary_segments: dict,
                           ratio_threshold: float = 2.0,
                           abs_min: int = 10) -> list:
    """Flag segments with drastic record-count swings between the two periods.

    Four kinds:
      - 'appeared'        — prior == 0, current > 0 (new segment)
      - 'disappeared'     — prior > 0, current == 0 (segment dropped out)
      - 'drastic_growth'  — current/prior >= ratio_threshold AND change >= abs_min
      - 'drastic_drop'    — current/prior <= 1/ratio_threshold AND |change| >= abs_min
    """
    alerts: list = []
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
