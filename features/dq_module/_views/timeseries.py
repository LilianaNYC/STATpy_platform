"""Time Series tab — port of pages/timeseries_page.py (+ the Port 2024 vs
Port 2025 scorecard table from pages/scorecard_page.py, which renders inside
this tab in the Dash app).

Sections:
  A — Components hero (4 big cards: current + Δ4Q + Δ8Q + sparkline)
  B — Macro sparkline grid (11 series)
  C — Multi-series overlay (raw / indexed / z-score, optional smoothing)
  D — Anomaly log (rolling 8Q z-score)
  E — Stability scorecard (volatility / slope / Δ4Q / Δ8Q)
  F — Correlation matrix + lag-correlation table
  G — Naive 4Q forecast (OLS extrapolation)
  H — Portfolio Scorecard (Port 2024 vs Port 2025, RAG)

All math is a Python port of the page's client-side JS (mean/std/OLS/Pearson/
rolling z-score) — no new server-side computation. Defaults to Historical.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from .common import (
    GRAPH_CFG, SECTION, SECTION_IN_GRID, SECTION_TITLE, empty_note, fmt, fmt_n,
    get_q, q_label, simple_table, spark, td,
)

TAB = "timeseries"


def _fmt_pct2(v):
    return fmt(v, 2) + "%"


def _fmt_signed_n(v):
    return ("+" if v >= 0 else "") + fmt_n(v)


TS_SERIES = [
    {"key": "completeness_pct", "label": "Overall Completeness %", "icon": "✅",
     "better": "high", "color": "#16a34a", "fmt": _fmt_pct2},
    {"key": "crit_missing_cols", "label": "Critical-missing cols (>25%)", "icon": "🔴",
     "better": "low", "color": "#dc2626", "fmt": fmt_n},
    {"key": "high_missing_cols", "label": "High-missing cols (>10%)", "icon": "🟠",
     "better": "low", "color": "#ea580c", "fmt": fmt_n},
    {"key": "avg_psi", "label": "Avg PSI (drift)", "icon": "📈",
     "better": "low", "color": "#dc2626", "fmt": lambda v: fmt(v, 3)},
    {"key": "max_psi", "label": "Max PSI", "icon": "📉",
     "better": "low", "color": "#7c2d12", "fmt": lambda v: fmt(v, 3)},
    {"key": "sig_drift_cols", "label": "Significant-drift cols (>0.20)", "icon": "⚠️",
     "better": "low", "color": "#ea580c", "fmt": fmt_n},
    {"key": "pop_psi", "label": "Population PSI", "icon": "👥",
     "better": "low", "color": "#2563eb", "fmt": lambda v: fmt(v, 3)},
    {"key": "total_accounts", "label": "Total Accounts", "icon": "📊",
     "better": "neutral", "color": "#0369a1", "fmt": fmt_n},
    {"key": "net_change", "label": "Net Account Change", "icon": "🔀",
     "better": "neutral", "color": "#7c3aed", "fmt": _fmt_signed_n},
    {"key": "new_accounts", "label": "New Accounts", "icon": "🆕",
     "better": "neutral", "color": "#16a34a", "fmt": fmt_n},
    {"key": "dropped_accounts", "label": "Dropped Accounts", "icon": "⬇️",
     "better": "neutral", "color": "#dc2626", "fmt": fmt_n},
]
TS_BY_KEY = {s["key"]: s for s in TS_SERIES}


# ── Math helpers (ports of the JS) ────────────────────────────────────────

def _clean(a):
    return [x for x in a if x is not None and math.isfinite(x)]


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _mean(a):
    v = _clean(a)
    return sum(v) / len(v) if v else None


def _std(a):
    v = _clean(a)
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def _ols(ys):
    pts = [(i, y) for i, y in enumerate(ys) if y is not None and math.isfinite(y)]
    if len(pts) < 2:
        return {"slope": None, "intercept": None, "r2": None, "n": len(pts)}
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    slope = num / den if den else 0.0
    intercept = my - slope * mx
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in pts)
    ss_tot = sum((y - my) ** 2 for _, y in pts)
    return {"slope": slope, "intercept": intercept,
            "r2": (1 - ss_res / ss_tot) if ss_tot else None, "n": n}


def _pearson(a, b):
    pairs = [(x, y) for x, y in zip(a, b)
             if x is not None and y is not None
             and math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 3:
        return None, len(pairs)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return (num / den if den else None), len(pairs)


def _zscore_series(values, window=8):
    out = []
    for i, v in enumerate(values):
        if v is None or not math.isfinite(v):
            out.append(None)
            continue
        baseline = _clean(values[max(0, i - window):i])
        if len(baseline) < 3:
            out.append(None)
            continue
        m, s = _mean(baseline), _std(baseline)
        out.append((v - m) / s if s else None)
    return out


def _moving_avg(values, window):
    if not window or window < 2:
        return list(values)
    out = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        sl = _clean(values[max(0, i - window + 1):i + 1])
        out.append(sum(sl) / len(sl) if sl else None)
    return out


# ── Series construction (port of _tsBuildSeries) ──────────────────────────

def build_series(metrics):
    all_q = metrics.get("quarters") or []
    ts = metrics.get("time_series") or {}
    comp_by_q = {r["quarter"]: r.get("value")
                 for r in ts.get("completeness_over_time") or []}
    psi_by_q = {r["quarter"]: r.get("avg_psi") for r in ts.get("psi_over_time") or []}
    pop_by_q = {r["quarter"]: r for r in ts.get("population_over_time") or []}
    psi_hm = ts.get("psi_heatmap") or {}
    psi_cols = list(psi_hm)

    max_psi_by_q, sig_by_q = {}, {}
    for q in all_q:
        max_p, sig_n = None, 0
        for col in psi_cols:
            v = (psi_hm.get(col) or {}).get(q)
            if v is None:
                continue
            if max_p is None or v > max_p:
                max_p = v
            if v > 0.20:
                sig_n += 1
        max_psi_by_q[q] = max_p
        sig_by_q[q] = sig_n if psi_cols else None

    crit_by_q, high_by_q = {}, {}
    for q in all_q:
        cols = (get_q(metrics, q).get("completeness") or {}).get("by_column") or []
        if not cols:
            crit_by_q[q] = high_by_q[q] = None
            continue
        c = sum(1 for r in cols if float(r.get("missing_pct") or 0) > 25)
        h = sum(1 for r in cols if float(r.get("missing_pct") or 0) > 10)
        crit_by_q[q], high_by_q[q] = c, h

    data = {
        "completeness_pct": [comp_by_q.get(q) for q in all_q],
        "crit_missing_cols": [crit_by_q.get(q) for q in all_q],
        "high_missing_cols": [high_by_q.get(q) for q in all_q],
        "avg_psi": [psi_by_q.get(q) for q in all_q],
        "max_psi": [max_psi_by_q.get(q) for q in all_q],
        "sig_drift_cols": [sig_by_q.get(q) for q in all_q],
        "pop_psi": [(pop_by_q.get(q) or {}).get("psi") for q in all_q],
        "total_accounts": [(pop_by_q.get(q) or {}).get("total") for q in all_q],
        "new_accounts": [(pop_by_q.get(q) or {}).get("new") for q in all_q],
        "dropped_accounts": [(pop_by_q.get(q) or {}).get("dropped") for q in all_q],
    }
    totals = data["total_accounts"]
    data["net_change"] = [
        None if v is None or i == 0 or totals[i - 1] is None else v - totals[i - 1]
        for i, v in enumerate(totals)]
    return {"quarters": all_q, "data": data}


def _window_indexes(all_q, window, start=None, end=None):
    """Window presets: tail-N for 4q/8q/12q, range filter for custom, else all."""
    n = {"4q": 4, "8q": 8, "12q": 12}.get(window)
    if n:
        return list(range(max(0, len(all_q) - n), len(all_q)))
    if window == "custom":
        return [i for i, q in enumerate(all_q)
                if (not start or q >= start) and (not end or q <= end)]
    return list(range(len(all_q)))  # "all"


def _delta_arrow(spec, d, fmt_abs=None):
    if d is None or not math.isfinite(d) or abs(d) < 1e-9:
        return html.Span("—", style={"color": "#64748b"})
    direction = "▲" if d > 0 else "▼"
    if spec["better"] == "neutral":
        c = "#64748b"
    elif spec["better"] == "high":
        c = "#16a34a" if d > 0 else "#dc2626"
    else:
        c = "#dc2626" if d > 0 else "#16a34a"
    num = fmt_n(d) if abs(d) >= 100 else fmt(d, 3)
    return html.Span(f"{direction} {'+' if d > 0 else ''}{num}",
                     style={"color": c, "fontWeight": "700"})


# ── Static sections (B sparkline grid + H scorecard) ─────────────────────

def _spark_grid(ts):
    cards = []
    for spec in TS_SERIES:
        vals = ts["data"][spec["key"]]
        tail = _clean(vals[-8:])
        last = vals[-1] if vals else None
        y_idx = len(vals) - 1 - 4
        yoy = (last - vals[y_idx]
               if y_idx >= 0 and last is not None and vals[y_idx] is not None else None)
        cards.append(html.Div([
            html.Div([
                html.Div(f"{spec['icon']} {spec['label']}",
                         style={"fontSize": "10px", "fontWeight": "700",
                                "color": "#0f172a"}),
                _delta_arrow(spec, yoy),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "gap": "6px"}),
            html.Div("—" if last is None else spec["fmt"](last),
                     style={"fontSize": "18px", "fontWeight": "800",
                            "color": spec["color"], "margin": "6px 0 0",
                            "lineHeight": "1"}),
            html.Div(spark(tail) if tail else "—",
                     style={"color": spec["color"], "fontFamily": "monospace",
                            "fontSize": "12px", "letterSpacing": "1px",
                            "marginTop": "4px"}),
            html.Div("last 8Q", style={"fontSize": "9px", "color": "#94a3b8",
                                       "marginTop": "2px"}),
        ], style={"background": "#fff", "border": "1px solid #e2e8f0",
                  "borderRadius": "6px", "padding": "10px"}))
    return html.Div(cards, style={"display": "grid",
                                  "gridTemplateColumns": "repeat(4, 1fr)",
                                  "gap": "10px"})


def _scorecard_section(metrics):
    """Port of pages/scorecard_page.py — renders inside this tab."""
    sc = metrics.get("scorecard") or {}
    rows = sc.get("rows") or []
    q24 = sc.get("quarter_24") or "Q4 2024"
    q25 = sc.get("quarter_25") or "Q4 2025"

    def rag_norm(r):
        return str(r or "").lower()

    def rag_bg(r):
        return {"red": "#fee2e2", "amber": "#fef9c3",
                "green": "#dcfce7"}.get(rag_norm(r), "#f8fafc")

    def rag_fg(r):
        return {"red": "#991b1b", "amber": "#92400e",
                "green": "#166534"}.get(rag_norm(r), "#475569")

    def sc_fmt(v):
        if v is None:
            return "—"
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return fmt_n(v) if float(v) == int(float(v)) else fmt(v, 3)
        return str(v)

    n_green = sum(1 for r in rows if rag_norm(r.get("rag")) == "green")
    n_amber = sum(1 for r in rows if rag_norm(r.get("rag")) == "amber")
    n_red = sum(1 for r in rows if rag_norm(r.get("rag")) == "red")

    def kpi(icon, label, n, color, sub):
        return html.Div([
            html.Div(icon, style={"fontSize": "15px"}),
            html.Div(label, style={"fontSize": "10px", "fontWeight": "700",
                                   "textTransform": "uppercase", "color": "#64748b"}),
            html.Div(str(n), style={"fontSize": "21px", "fontWeight": "700",
                                    "color": color}),
            html.Div(sub, style={"fontSize": "11px", "color": "#94a3b8"}),
        ], style={"background": "#fff", "border": "1px solid #e2e8f0",
                  "borderRadius": "10px", "padding": "14px"})

    body = []
    for r in rows:
        rag = r.get("rag")
        body.append(html.Tr([
            td(r.get("metric"), fontWeight="600"),
            td(sc_fmt(r.get("v24")), textAlign="right"),
            td(sc_fmt(r.get("v25")), textAlign="right"),
            td(r.get("delta") or "—", textAlign="right", fontWeight="600",
               color=rag_fg(rag)),
            td(html.Span(str(rag or "—").capitalize(),
                         style={"display": "inline-block", "padding": "2px 8px",
                                "borderRadius": "4px", "fontSize": "11px",
                                "fontWeight": "700", "background": rag_bg(rag),
                                "color": rag_fg(rag)}), textAlign="center"),
            td(r.get("red_flag") or "", fontSize="11px", color="#64748b"),
        ], style={"background": rag_bg(rag)}))

    bar = go.Figure(go.Bar(
        y=["Green", "Amber", "Red"], x=[n_green, n_amber, n_red], orientation="h",
        marker={"color": ["#16a34a", "#d97706", "#dc2626"]},
        text=[n_green, n_amber, n_red], textposition="outside"))
    bar.update_layout(margin={"t": 5, "r": 40, "b": 30, "l": 60}, height=160,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis={"gridcolor": "#f1f5f9", "tickfont": {"size": 9}},
                      yaxis={"tickfont": {"size": 10}}, showlegend=False)

    return html.Div([
        html.Div(f"H · Portfolio Scorecard — {q24} vs {q25} · fixed snapshot "
                 "comparison (ignores the window above)", style=SECTION_TITLE),
        html.Div("Side-by-side comparison of key DQ metrics across the 2024 and 2025 "
                 "portfolios. RAG status highlights material changes.",
                 style={"fontSize": "11px", "color": "#64748b", "marginBottom": "10px"}),
        html.Div([
            kpi("🟢", "Green", n_green, "#166534", "metrics improved / stable"),
            kpi("🟡", "Amber", n_amber, "#92400e", "metrics need monitoring"),
            kpi("🔴", "Red", n_red, "#991b1b", "metrics require action"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
                  "gap": "12px", "marginBottom": "14px"}),
        (simple_table([f"Metric", f"{q24}", f"{q25}", "Change", "RAG",
                       "Alert Condition"], body,
                      header_styles=[None, {"textAlign": "right"},
                                     {"textAlign": "right"}, {"textAlign": "right"},
                                     {"textAlign": "center"}, None])
         if body else empty_note("Scorecard data not available — run pipeline with "
                                 "both portfolio files")),
        html.Div("RAG Status Distribution",
                 style=dict(SECTION_TITLE, marginTop="16px")),
        dcc.Graph(figure=bar, config=GRAPH_CFG),
    ], style=SECTION)


# ── Window picker (replaces the generic comparison-mode bar) ──────────────

def _window_picker(metrics: dict) -> html.Div:
    quarters = metrics.get("quarters") or []
    q_opts_asc = [{"label": q_label(q), "value": q} for q in quarters]
    dd_style = {"width": "150px", "fontSize": "11px", "display": "inline-block"}
    lab = {"fontSize": "11px", "color": "#64748b", "margin": "0 4px 0 10px"}
    return html.Div([
        html.Div([
            html.Span("WINDOW", style={"fontSize": "10px", "fontWeight": "700",
                                       "color": "#64748b", "letterSpacing": ".05em",
                                       "marginRight": "12px"}),
            dcc.RadioItems(
                id=f"dqd-{TAB}-window",
                options=[{"label": "Last 4Q", "value": "4q"},
                         {"label": "Last 8Q", "value": "8q"},
                         {"label": "Last 12Q", "value": "12q"},
                         {"label": "All history", "value": "all"},
                         {"label": "Custom range…", "value": "custom"}],
                value="12q", inline=True,
                labelStyle={"marginRight": "16px", "fontSize": "12px"},
                style={"display": "inline-block"}),
            html.Span(id=f"dqd-{TAB}-window-note",
                      style={"fontSize": "11px", "color": "#475569",
                             "fontFamily": "monospace", "marginLeft": "10px"}),
        ]),
        html.Div([
            html.Span("From", style=dict(lab, marginLeft="0")),
            dcc.Dropdown(id=f"dqd-{TAB}-win-start", options=q_opts_asc,
                         value=quarters[0] if quarters else None,
                         clearable=False, style=dd_style),
            html.Span("→ To", style=lab),
            dcc.Dropdown(id=f"dqd-{TAB}-win-end", options=q_opts_asc,
                         value=quarters[-1] if quarters else None,
                         clearable=False, style=dd_style),
        ], id=f"dqd-{TAB}-window-custom",
            style={"display": "none"}),
    ], style=SECTION)


# ── Layout ────────────────────────────────────────────────────────────────

def layout(metrics: dict):
    ts = build_series(metrics)
    series_opts = [{"label": f"{s['icon']} {s['label']}", "value": s["key"]}
                   for s in TS_SERIES]

    def dd_label(text):
        return html.Span(text, style={"fontSize": "10px", "color": "#64748b",
                                      "fontWeight": "700",
                                      "textTransform": "uppercase"})

    return [
        html.Div([
            html.H2(id=f"dqd-{TAB}-header", style={"margin": "0 0 6px",
                                                   "fontSize": "20px"}),
            html.P("Cross-cutting trend exploration over Port 2025. Pick a window — "
                   "sections A and C–G follow it; B is a fixed full-history "
                   "reference; H is a fixed Port 2024 vs Port 2025 snapshot "
                   "comparison.",
                   style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
        ], style=SECTION),

        _window_picker(metrics),

        html.Div("A · Components", style={"fontSize": "10px", "fontWeight": "700",
                                          "color": "#64748b",
                                          "textTransform": "uppercase",
                                          "letterSpacing": ".05em",
                                          "margin": "6px 0"}),
        html.Div(id=f"dqd-{TAB}-hero",
                 style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)",
                        "gap": "12px", "marginBottom": "18px"}),

        html.Div([
            html.Div("B · Macro trends — full history reference "
                     "(does not follow the window)", style=SECTION_TITLE),
            html.Div("Every monitored series with its current value, last-8Q sparkline, "
                     "and YoY arrow (green = improving move, red = worsening).",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            _spark_grid(ts),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div("C · Multi-series overlay — pick up to 4",
                         style=dict(SECTION_TITLE, margin=0)),
                html.Div([
                    dd_label("Mode"),
                    dcc.Dropdown(id=f"dqd-{TAB}-overlay-mode", clearable=False,
                                 value="zscore",
                                 options=[{"label": "Raw", "value": "raw"},
                                          {"label": "Indexed (= 100 at start)",
                                           "value": "indexed"},
                                          {"label": "Z-score (mean 0 / std 1)",
                                           "value": "zscore"}],
                                 style={"width": "190px", "fontSize": "11px"}),
                    dd_label("Smooth"),
                    dcc.Dropdown(id=f"dqd-{TAB}-overlay-smooth", clearable=False,
                                 value=0,
                                 options=[{"label": "None", "value": 0},
                                          {"label": "4Q MA", "value": 4},
                                          {"label": "8Q MA", "value": 8}],
                                 style={"width": "110px", "fontSize": "11px"}),
                ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "8px",
                      "marginBottom": "8px"}),
            dcc.Checklist(id=f"dqd-{TAB}-overlay-sel",
                          options=series_opts,
                          value=["completeness_pct", "avg_psi", "pop_psi"],
                          inline=True,
                          labelStyle={"marginRight": "14px", "fontSize": "11px"}),
            dcc.Graph(id=f"dqd-{TAB}-overlay-chart", config=GRAPH_CFG),
            html.Div(id=f"dqd-{TAB}-overlay-note",
                     style={"marginTop": "8px", "fontSize": "10px",
                            "color": "#64748b", "fontStyle": "italic"}),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div("D · Anomaly log — rolling 8Q baseline",
                         style=dict(SECTION_TITLE, margin=0)),
                html.Div([
                    dd_label("Series"),
                    dcc.Dropdown(id=f"dqd-{TAB}-anomaly-series", clearable=False,
                                 value="all",
                                 options=([{"label": "All series", "value": "all"}] +
                                          series_opts),
                                 style={"width": "230px", "fontSize": "11px"}),
                    dd_label("Min severity"),
                    dcc.Dropdown(id=f"dqd-{TAB}-anomaly-z", clearable=False, value=2,
                                 options=[{"label": "|z| ≥ 2 (mild)", "value": 2},
                                          {"label": "|z| ≥ 3 (moderate)", "value": 3},
                                          {"label": "|z| ≥ 4 (strong)", "value": 4}],
                                 style={"width": "160px", "fontSize": "11px"}),
                ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "8px",
                      "marginBottom": "8px"}),
            html.Div("For each series, compare every quarter's value to the rolling "
                     "mean ± σ of the prior 8 quarters. Breakouts beyond the threshold "
                     "are listed newest first.",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-anomaly-feed",
                     style={"maxHeight": "380px", "overflowY": "auto"}),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div("E · Stability scorecard", style=dict(SECTION_TITLE, margin=0)),
                html.Div([
                    dd_label("Sort by"),
                    dcc.Dropdown(id=f"dqd-{TAB}-score-sort", clearable=False,
                                 value="cv_desc",
                                 options=[
                                     {"label": "Volatility (CV) ↓", "value": "cv_desc"},
                                     {"label": "Volatility (CV) ↑", "value": "cv_asc"},
                                     {"label": "|Slope| ↓", "value": "slope_abs_desc"},
                                     {"label": "|Δ 8Q| ↓", "value": "d8_abs_desc"},
                                     {"label": "Name A→Z", "value": "label_asc"}],
                                 style={"width": "180px", "fontSize": "11px"}),
                ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "8px",
                      "marginBottom": "8px"}),
            html.Div("For every series over the visible window: latest value, change "
                     "vs 4 / 8 Q ago, coefficient of variation (σ / |mean| × 100), OLS "
                     "trend slope, and the worst / best quarters.",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-scorecard", style={"overflowX": "auto"}),
        ], style=SECTION),

        html.Div([
            html.Div("F · Cross-metric correlation", style=SECTION_TITLE),
            html.Div("Pearson correlation across the visible window. Correlation is "
                     "descriptive — it doesn't imply causation.",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div([
                dcc.Graph(id=f"dqd-{TAB}-corr-matrix", config=GRAPH_CFG),
                html.Div([
                    html.Div("Lag analysis", style={"fontSize": "11px",
                                                    "fontWeight": "700",
                                                    "color": "#0f172a",
                                                    "textTransform": "uppercase",
                                                    "letterSpacing": ".05em",
                                                    "marginBottom": "6px"}),
                    html.Div("Cross-correlation at lags −2…+4 quarters. If r peaks at "
                             "a non-zero lag, one series may lead the other.",
                             style={"fontSize": "11px", "color": "#64748b",
                                    "marginBottom": "10px"}),
                    html.Div([dd_label("A"),
                              dcc.Dropdown(id=f"dqd-{TAB}-lag-a", clearable=False,
                                           value="completeness_pct",
                                           options=series_opts,
                                           style={"flex": "1", "fontSize": "11px"})],
                             style={"display": "flex", "gap": "6px",
                                    "alignItems": "center", "marginBottom": "6px"}),
                    html.Div([dd_label("B"),
                              dcc.Dropdown(id=f"dqd-{TAB}-lag-b", clearable=False,
                                           value="avg_psi", options=series_opts,
                                           style={"flex": "1", "fontSize": "11px"})],
                             style={"display": "flex", "gap": "6px",
                                    "alignItems": "center", "marginBottom": "10px"}),
                    html.Div(id=f"dqd-{TAB}-lag-table"),
                ]),
            ], style={"display": "grid", "gridTemplateColumns": "2fr 1fr",
                      "gap": "16px", "alignItems": "start"}),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div("G · Naive forecast", style=dict(SECTION_TITLE, margin=0)),
                html.Div([
                    dd_label("Series"),
                    dcc.Dropdown(id=f"dqd-{TAB}-forecast-key", clearable=False,
                                 value="completeness_pct", options=series_opts,
                                 style={"width": "230px", "fontSize": "11px"}),
                    dd_label("Horizon"),
                    dcc.Dropdown(id=f"dqd-{TAB}-forecast-horizon", clearable=False,
                                 value=4,
                                 options=[{"label": "+2 Q", "value": 2},
                                          {"label": "+4 Q", "value": 4},
                                          {"label": "+8 Q", "value": 8}],
                                 style={"width": "100px", "fontSize": "11px"}),
                ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "8px",
                      "marginBottom": "8px"}),
            html.Div(["⚠ ", html.Strong("Naive extrapolation only."),
                      " OLS fit on the last 12 visible quarters projected forward. "
                      "The shaded band is ±1 residual σ — directional guidance, not "
                      "point estimates."],
                     style={"background": "#fffbeb", "border": "1px solid #fcd34d",
                            "borderRadius": "6px", "padding": "10px 14px",
                            "marginBottom": "12px", "fontSize": "11px",
                            "color": "#92400e"}),
            dcc.Graph(id=f"dqd-{TAB}-forecast-chart", config=GRAPH_CFG),
            html.Div(id=f"dqd-{TAB}-forecast-meta",
                     style={"marginTop": "8px", "fontSize": "11px",
                            "color": "#64748b"}),
        ], style=SECTION),

        _scorecard_section(metrics),
    ]


# ── Callbacks ─────────────────────────────────────────────────────────────

def register_callbacks(app, metrics: dict):
    ts = build_series(metrics)

    @app.callback(
        Output(f"dqd-{TAB}-window-custom", "style"),
        Input(f"dqd-{TAB}-window", "value"),
    )
    def _toggle_custom(window):
        if window == "custom":
            return {"display": "flex", "alignItems": "center", "marginTop": "8px"}
        return {"display": "none"}

    @app.callback(
        Output(f"dqd-{TAB}-header", "children"),
        Output(f"dqd-{TAB}-window-note", "children"),
        Output(f"dqd-{TAB}-hero", "children"),
        Output(f"dqd-{TAB}-overlay-chart", "figure"),
        Output(f"dqd-{TAB}-overlay-note", "children"),
        Output(f"dqd-{TAB}-anomaly-feed", "children"),
        Output(f"dqd-{TAB}-scorecard", "children"),
        Output(f"dqd-{TAB}-corr-matrix", "figure"),
        Output(f"dqd-{TAB}-lag-table", "children"),
        Output(f"dqd-{TAB}-forecast-chart", "figure"),
        Output(f"dqd-{TAB}-forecast-meta", "children"),
        Input(f"dqd-{TAB}-window", "value"),
        Input(f"dqd-{TAB}-win-start", "value"),
        Input(f"dqd-{TAB}-win-end", "value"),
        Input(f"dqd-{TAB}-overlay-sel", "value"),
        Input(f"dqd-{TAB}-overlay-mode", "value"),
        Input(f"dqd-{TAB}-overlay-smooth", "value"),
        Input(f"dqd-{TAB}-anomaly-series", "value"),
        Input(f"dqd-{TAB}-anomaly-z", "value"),
        Input(f"dqd-{TAB}-score-sort", "value"),
        Input(f"dqd-{TAB}-lag-a", "value"),
        Input(f"dqd-{TAB}-lag-b", "value"),
        Input(f"dqd-{TAB}-forecast-key", "value"),
        Input(f"dqd-{TAB}-forecast-horizon", "value"),
    )
    def _update(window, win_start, win_end,
                overlay_sel, overlay_mode, overlay_smooth,
                anomaly_series, anomaly_z, score_sort,
                lag_a, lag_b, forecast_key, forecast_horizon):
        window = window or "12q"
        win_idx = _window_indexes(ts["quarters"], window, win_start, win_end)
        win_q = [ts["quarters"][i] for i in win_idx]
        wd = {s["key"]: [ts["data"][s["key"]][i] for i in win_idx]
              for s in TS_SERIES}
        x_labels = [q_label(q) for q in win_q]

        header = f"Time Series Analytics — {len(win_q)} quarter(s) in view"
        window_note = (f"{len(win_q)} Q · {q_label(win_q[0])} → {q_label(win_q[-1])}"
                       if win_q else "no quarters in range")

        # ── A · Hero ──
        hero = []
        for key in ("completeness_pct", "avg_psi", "pop_psi", "total_accounts"):
            spec = TS_BY_KEY[key]
            series = wd[key]
            last = series[-1] if series else None
            i4, i8 = len(series) - 1 - 4, len(series) - 1 - 8
            d4 = (last - series[i4] if i4 >= 0 and last is not None
                  and series[i4] is not None else None)
            d8 = (last - series[i8] if i8 >= 0 and last is not None
                  and series[i8] is not None else None)
            tail = _clean(series)
            hero.append(html.Div([
                html.Div(f"{spec['icon']} {spec['label']}",
                         style={"fontSize": "10px", "fontWeight": "700",
                                "color": "#64748b", "textTransform": "uppercase",
                                "letterSpacing": ".05em"}),
                html.Div("—" if last is None else spec["fmt"](last),
                         style={"fontSize": "28px", "fontWeight": "800",
                                "color": "#0f172a", "margin": "6px 0 4px",
                                "lineHeight": "1"}),
                html.Div([html.Span(["Δ 4Q ", _delta_arrow(spec, d4)]),
                          html.Span(["Δ 8Q ", _delta_arrow(spec, d8)])],
                         style={"display": "flex", "gap": "14px",
                                "fontSize": "11px", "color": "#64748b"}),
                html.Div(spark(tail) if tail else "—",
                         style={"marginTop": "8px", "color": spec["color"],
                                "fontFamily": "monospace", "fontSize": "14px",
                                "letterSpacing": "1px"}),
                html.Div(f"{q_label(win_q[0]) if win_q else ''} → "
                         f"{q_label(win_q[-1]) if win_q else ''}",
                         style={"fontSize": "9px", "color": "#94a3b8",
                                "marginTop": "2px"}),
            ], style={"background": "#fff", "border": "1px solid #e2e8f0",
                      "borderRadius": "10px", "padding": "14px",
                      "borderLeft": f"4px solid {spec['color']}"}))

        # ── C · Overlay ──
        sel = (overlay_sel or [])[:4] or ["completeness_pct"]
        overlay = go.Figure()
        y_axes = {}
        for idx, key in enumerate(sel):
            spec = TS_BY_KEY.get(key)
            if not spec:
                continue
            values = list(wd[key])
            if overlay_smooth:
                values = _moving_avg(values, int(overlay_smooth))
            if overlay_mode == "indexed":
                base = next((v for v in values
                             if v is not None and math.isfinite(v) and v != 0), None)
                if base:
                    values = [None if v is None else v / base * 100 for v in values]
            elif overlay_mode == "zscore":
                m, s = _mean(values), _std(values)
                if s:
                    values = [None if v is None else (v - m) / s for v in values]
            trace = go.Scatter(x=x_labels, y=values, name=spec["label"],
                               mode="lines+markers",
                               line={"color": spec["color"], "width": 2},
                               marker={"size": 4}, connectgaps=True)
            if overlay_mode == "raw" and idx > 0:
                axis = f"y{idx + 1}"
                trace.update(yaxis=axis)
                y_axes[f"yaxis{idx + 1}"] = {
                    "overlaying": "y", "side": "right" if idx % 2 else "left",
                    "showgrid": False,
                    "title": {"text": spec["label"],
                              "font": {"size": 9, "color": spec["color"]}},
                    "tickfont": {"size": 9, "color": spec["color"]}}
            overlay.add_trace(trace)
        y_label = ("Index (= 100 at start)" if overlay_mode == "indexed"
                   else "Z-score (σ units)" if overlay_mode == "zscore"
                   else (TS_BY_KEY[sel[0]]["label"] if sel else "Value"))
        overlay.update_layout(
            margin={"t": 30, "r": 60, "b": 60, "l": 60}, height=340,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"tickangle": -45, "tickfont": {"size": 9}, "showgrid": False,
                   "title": {"text": "Quarter", "font": {"size": 10}}},
            yaxis={"title": y_label, "gridcolor": "#f1f5f9", "tickfont": {"size": 9}},
            legend={"orientation": "h", "y": 1.12, "font": {"size": 10}},
            showlegend=True, **y_axes)
        overlay_note = {
            "raw": "Raw: each series on its own y-axis. Magnitudes preserved; "
                   "co-movement harder to read.",
            "indexed": "Indexed: every series rebased to 100 at the first visible "
                       "quarter. Shows relative growth, not absolute levels.",
        }.get(overlay_mode, "Z-score: each series normalized to mean 0, std 1 over the "
                            "visible window. Best view for spotting co-movement.")

        # ── D · Anomalies ──
        z_thresh = int(anomaly_z or 2)
        specs = (TS_SERIES if anomaly_series in (None, "all")
                 else [TS_BY_KEY[anomaly_series]])
        events = []
        for spec in specs:
            values = ts["data"][spec["key"]]
            z = _zscore_series(values, 8)
            for i in win_idx:
                zi = z[i]
                if zi is None or abs(zi) < z_thresh:
                    continue
                baseline = _clean(values[max(0, i - 8):i])
                events.append({"q": ts["quarters"][i], "q_idx": i, "spec": spec,
                               "value": values[i], "z": zi,
                               "mean": _mean(baseline), "std": _std(baseline)})
        events.sort(key=lambda e: -e["q_idx"])
        if not events:
            feed = html.Div(f"✓ No anomalies in the visible window at "
                            f"|z| ≥ {z_thresh}.",
                            style={"padding": "24px", "color": "#16a34a",
                                   "fontSize": "13px", "textAlign": "center",
                                   "background": "#dcfce7", "borderRadius": "8px"})
        else:
            items = []
            for ev in events[:80]:
                a = abs(ev["z"])
                sv = ({"label": "Strong", "tone": "#7f1d1d", "bg": "#fee2e2",
                       "icon": "🔴"} if a >= 4 else
                      {"label": "Moderate", "tone": "#9a3412", "bg": "#ffedd5",
                       "icon": "🟠"} if a >= 3 else
                      {"label": "Mild", "tone": "#854d0e", "bg": "#fef9c3",
                       "icon": "🟡"})
                f_ = ev["spec"]["fmt"]
                items.append(html.Div([
                    html.Div(sv["icon"], style={"fontSize": "18px"}),
                    html.Div([
                        html.Div([
                            html.Span([html.Strong(q_label(ev["q"]),
                                                   style={"fontFamily": "monospace"}),
                                       " · ",
                                       html.Span(ev["spec"]["label"],
                                                 style={"color": ev["spec"]["color"],
                                                        "fontWeight": "700"})]),
                            html.Span(f"{sv['label']} · |z|={fmt(a, 1)}",
                                      style={"fontSize": "9px", "fontWeight": "700",
                                             "color": "#fff",
                                             "background": sv["tone"],
                                             "padding": "2px 8px",
                                             "borderRadius": "8px",
                                             "textTransform": "uppercase"}),
                        ], style={"display": "flex",
                                  "justifyContent": "space-between", "gap": "8px",
                                  "flexWrap": "wrap"}),
                        html.Div([("spiked" if ev["z"] > 0 else "dropped"), " to ",
                                  html.Strong(f_(ev["value"])),
                                  " vs rolling baseline ",
                                  html.Strong("—" if ev["mean"] is None
                                              else f_(ev["mean"])),
                                  " ± ",
                                  ("—" if ev["std"] is None else f_(ev["std"])),
                                  html.Span(" (last 8Q window)",
                                            style={"color": "#94a3b8"})],
                                 style={"fontSize": "11px", "color": "#64748b",
                                        "marginTop": "3px"}),
                    ], style={"flex": "1"}),
                ], style={"display": "flex", "gap": "12px", "padding": "10px 12px",
                          "border": f"1px solid {sv['bg']}",
                          "borderLeft": f"3px solid {sv['tone']}",
                          "background": "#fff", "borderRadius": "6px",
                          "marginBottom": "6px"}))
            if len(events) > 80:
                items.append(html.Div(
                    f"… {len(events) - 80} more anomalies (showing newest 80).",
                    style={"textAlign": "center", "fontSize": "11px",
                           "color": "#64748b", "padding": "8px",
                           "fontStyle": "italic"}))
            feed = html.Div(items)

        # ── E · Stability scorecard ──
        rows = []
        for spec in TS_SERIES:
            values = wd[spec["key"]]
            v_clean = _clean(values)
            last = v_clean[-1] if v_clean else None
            mean, std = _mean(v_clean), _std(v_clean)
            cv = (std / abs(mean) * 100
                  if std is not None and mean is not None and abs(mean) > 1e-9
                  else None)
            i4, i8 = len(values) - 1 - 4, len(values) - 1 - 8
            d4 = (last - values[i4] if i4 >= 0 and last is not None
                  and values[i4] is not None else None)
            d8 = (last - values[i8] if i8 >= 0 and last is not None
                  and values[i8] is not None else None)
            ols = _ols(values)
            worst_i = best_i = None
            worst_v = best_v = None
            for i, v in enumerate(values):
                if v is None or not math.isfinite(v):
                    continue
                lo_is_worst = spec["better"] == "high" or spec["better"] == "neutral"
                if lo_is_worst:
                    if worst_v is None or v < worst_v:
                        worst_v, worst_i = v, i
                    if best_v is None or v > best_v:
                        best_v, best_i = v, i
                else:
                    if worst_v is None or v > worst_v:
                        worst_v, worst_i = v, i
                    if best_v is None or v < best_v:
                        best_v, best_i = v, i
            rows.append({"spec": spec, "last": last, "cv": cv, "d4": d4, "d8": d8,
                         "slope": ols["slope"], "v_clean": v_clean,
                         "worst_q": win_q[worst_i] if worst_i is not None else None,
                         "worst_v": worst_v,
                         "best_q": win_q[best_i] if best_i is not None else None,
                         "best_v": best_v})

        def safe(v, default):
            return default if v is None or not math.isfinite(v) else v

        sort = score_sort or "cv_desc"
        if sort == "cv_desc":
            rows.sort(key=lambda r: -safe(r["cv"], -math.inf))
        elif sort == "cv_asc":
            rows.sort(key=lambda r: safe(r["cv"], math.inf))
        elif sort == "slope_abs_desc":
            rows.sort(key=lambda r: -abs(safe(r["slope"], 0)))
        elif sort == "d8_abs_desc":
            rows.sort(key=lambda r: -abs(safe(r["d8"], 0)))
        else:
            rows.sort(key=lambda r: r["spec"]["label"])

        def d_color(spec, d):
            if d is None or not math.isfinite(d) or abs(d) < 1e-9:
                return "#64748b"
            if spec["better"] == "neutral":
                return "#64748b"
            if spec["better"] == "high":
                return "#16a34a" if d > 0 else "#dc2626"
            return "#dc2626" if d > 0 else "#16a34a"

        def cv_color(cv):
            if cv is None:
                return "#64748b"
            return "#dc2626" if cv > 40 else "#d97706" if cv > 20 else "#16a34a"

        body = []
        for r in rows:
            spec = r["spec"]
            f_ = spec["fmt"]
            body.append(html.Tr([
                td([html.Span(spec["icon"], style={"color": spec["color"]}),
                    f" {spec['label']}"], fontWeight="600", color="#0f172a"),
                td("—" if r["last"] is None else f_(r["last"]), textAlign="right",
                   fontWeight="600"),
                td("—" if r["d4"] is None
                   else ("+" if r["d4"] >= 0 else "") + f_(r["d4"]),
                   textAlign="right", fontWeight="600", color=d_color(spec, r["d4"])),
                td("—" if r["d8"] is None
                   else ("+" if r["d8"] >= 0 else "") + f_(r["d8"]),
                   textAlign="right", fontWeight="600", color=d_color(spec, r["d8"])),
                td("—" if r["cv"] is None else f"{fmt(r['cv'], 1)}%",
                   textAlign="right", fontWeight="600", color=cv_color(r["cv"])),
                td("—" if r["slope"] is None
                   else ("+" if r["slope"] >= 0 else "") + fmt(r["slope"], 4) + "/Q",
                   textAlign="right", fontFamily="monospace"),
                td([q_label(r["worst_q"]) if r["worst_q"] else "—",
                    html.Span("" if r["worst_v"] is None
                              else f" ({f_(r['worst_v'])})",
                              style={"color": "#dc2626"})],
                   fontSize="10px", color="#64748b"),
                td([q_label(r["best_q"]) if r["best_q"] else "—",
                    html.Span("" if r["best_v"] is None
                              else f" ({f_(r['best_v'])})",
                              style={"color": "#16a34a"})],
                   fontSize="10px", color="#64748b"),
                td(spark(r["v_clean"]) if r["v_clean"] else "—",
                   color=spec["color"], fontFamily="monospace",
                   letterSpacing="1px", textAlign="center"),
            ]))
        right = {"textAlign": "right"}
        scorecard = simple_table(
            ["Series", "Latest", "Δ 4Q", "Δ 8Q", "CV %", "Slope", "Worst Q",
             "Best Q", "Sparkline"], body,
            header_styles=[None, right, right, right, right, right, None, None,
                           {"textAlign": "center"}])

        # ── F · Correlation matrix + lag table ──
        labels = [s["label"] for s in TS_SERIES]
        z, text = [], []
        for i, si in enumerate(TS_SERIES):
            row, trow = [], []
            for j, sj in enumerate(TS_SERIES):
                if i == j:
                    row.append(1.0)
                    trow.append("1.00")
                    continue
                r, n = _pearson(wd[si["key"]], wd[sj["key"]])
                row.append(r)
                trow.append("—" if r is None else f"{fmt(r, 2)}<br>n={n}")
            z.append(row)
            text.append(trow)
        corr = go.Figure(go.Heatmap(
            z=z, x=labels, y=labels, text=text, texttemplate="%{text}",
            textfont={"size": 8},
            colorscale=[[0, "#dc2626"], [0.5, "#ffffff"], [1, "#2563eb"]],
            zmin=-1, zmax=1, zmid=0, showscale=True,
            colorbar={"title": "r", "tickfont": {"size": 9}, "len": 0.7},
            hovertemplate="%{y}<br>↔ %{x}<br>r = %{z:.2f}<extra></extra>"))
        corr.update_layout(margin={"t": 20, "r": 20, "b": 140, "l": 180}, height=500,
                           xaxis={"tickangle": -45, "tickfont": {"size": 9}},
                           yaxis={"tickfont": {"size": 9}, "autorange": "reversed"},
                           paper_bgcolor="rgba(0,0,0,0)",
                           plot_bgcolor="rgba(0,0,0,0)")

        a, b = wd.get(lag_a) or [], wd.get(lag_b) or []
        lag_rows_data = []
        for k in (-2, -1, 0, 1, 2, 3, 4):
            if k == 0:
                r, n = _pearson(a, b)
            elif k > 0:
                r, n = _pearson(a[:len(a) - k], b[k:])
            else:
                kk = -k
                r, n = _pearson(a[kk:], b[:len(b) - kk])
            lag_rows_data.append({"k": k, "r": r, "n": n})
        peak_idx, peak_abs = 0, -1.0
        for i, rr in enumerate(lag_rows_data):
            if rr["r"] is not None and abs(rr["r"]) > peak_abs:
                peak_abs, peak_idx = abs(rr["r"]), i
        lag_body = []
        for i, rr in enumerate(lag_rows_data):
            is_peak = i == peak_idx and rr["r"] is not None
            interp = ("contemporaneous" if rr["k"] == 0
                      else f"A leads B by {rr['k']}Q" if rr["k"] > 0
                      else f"B leads A by {-rr['k']}Q")
            lag_body.append(html.Tr([
                td(f"{'+' if rr['k'] >= 0 else ''}{rr['k']}", textAlign="center",
                   fontFamily="monospace"),
                td("—" if rr["r"] is None else fmt(rr["r"], 2), textAlign="center",
                   fontWeight="700",
                   color="#64748b" if rr["r"] is None
                   else ("#2563eb" if rr["r"] > 0 else "#dc2626")),
                td(str(rr["n"]), textAlign="center", color="#64748b"),
                td([interp, html.Strong(" ← peak", style={"color": "#854d0e"})
                    if is_peak else ""], fontSize="10px", color="#64748b"),
            ], style={"background": "#fef9c3"} if is_peak else None))
        lag_table = html.Div([
            simple_table(["Lag (Q)", "r", "n", ""], lag_body),
            html.Div(f"A = {TS_BY_KEY[lag_a]['label'] if lag_a in TS_BY_KEY else '—'} "
                     f"· B = {TS_BY_KEY[lag_b]['label'] if lag_b in TS_BY_KEY else '—'}. "
                     "Positive lag k means A predicts B by k quarters.",
                     style={"marginTop": "8px", "fontSize": "10px",
                            "color": "#64748b", "fontStyle": "italic"}),
        ])

        # ── G · Forecast ──
        spec = TS_BY_KEY.get(forecast_key) or TS_SERIES[0]
        values = wd[spec["key"]]
        horizon = int(forecast_horizon or 4)
        fit_n = min(12, len(values))
        fit_vals = values[len(values) - fit_n:]
        clean_fit = [(i, y) for i, y in enumerate(fit_vals)
                     if y is not None and math.isfinite(y)]
        forecast = go.Figure()
        meta = ""
        if len(clean_fit) < 3:
            forecast.update_layout(
                annotations=[{"text": "Not enough data in the fit window for a "
                                      "meaningful projection.",
                              "showarrow": False, "font": {"size": 12,
                                                           "color": "#94a3b8"}}],
                xaxis={"visible": False}, yaxis={"visible": False},
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=300)
        else:
            n = len(clean_fit)
            mx = sum(p[0] for p in clean_fit) / n
            my = sum(p[1] for p in clean_fit) / n
            num = sum((x - mx) * (y - my) for x, y in clean_fit)
            den = sum((x - mx) ** 2 for x, _ in clean_fit)
            slope = num / den if den else 0.0
            intercept = my - slope * mx
            ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in clean_fit)
            sigma = math.sqrt(ss_res / max(1, n - 2))

            fc_labels = []
            last_q = win_q[-1] if win_q else "2025Q4"
            yr, qtr = int(str(last_q)[:4]), int(str(last_q)[5])
            for _h in range(horizon):
                qtr += 1
                if qtr > 4:
                    qtr, yr = 1, yr + 1
                fc_labels.append(f"{yr} Q{qtr}")
            y_fc = [slope * (fit_n - 1 + h) + intercept for h in range(1, horizon + 1)]
            forecast.add_trace(go.Scatter(
                x=x_labels, y=values, name="Historical", mode="lines+markers",
                line={"color": spec["color"], "width": 2}, marker={"size": 3},
                connectgaps=True))
            forecast.add_trace(go.Scatter(
                x=fc_labels, y=[v + sigma for v in y_fc], mode="lines",
                line={"color": spec["color"], "width": 0}, showlegend=False,
                hoverinfo="skip"))
            forecast.add_trace(go.Scatter(
                x=fc_labels, y=[v - sigma for v in y_fc], mode="lines",
                name="Uncertainty band", line={"color": spec["color"], "width": 0},
                fill="tonexty", fillcolor=_rgba(spec["color"], 0.2),
                hovertemplate="σ band: %{y:.3f}<extra></extra>"))
            forecast.add_trace(go.Scatter(
                x=fc_labels, y=y_fc, name=f"Forecast +{horizon}Q",
                mode="lines+markers",
                line={"color": spec["color"], "width": 2, "dash": "dash"},
                marker={"size": 4, "symbol": "diamond"}))
            forecast.update_layout(
                margin={"t": 20, "r": 20, "b": 60, "l": 60}, height=300,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis={"tickangle": -45, "tickfont": {"size": 9}, "showgrid": False,
                       "title": {"text": "Quarter", "font": {"size": 10}}},
                yaxis={"title": spec["label"], "gridcolor": "#f1f5f9",
                       "tickfont": {"size": 9}},
                legend={"orientation": "h", "y": 1.12, "font": {"size": 10}},
                shapes=([{"type": "line", "x0": x_labels[-1], "x1": x_labels[-1],
                          "yref": "paper", "y0": 0, "y1": 1,
                          "line": {"color": "#cbd5e1", "width": 1, "dash": "dot"}}]
                        if x_labels else []))
            fit_window = (f"{q_label(win_q[-fit_n])} → {q_label(win_q[-1])}"
                          if len(win_q) >= fit_n and win_q else "visible window")
            meta = html.Span([
                f"Fit: OLS on the last ", html.Strong(str(n)),
                f" non-null points ({fit_window}) · slope = {fmt(slope, 4)}/Q · "
                f"residual σ = {fmt(sigma, 4)}. Forecast next {horizon} quarters at "
                "constant slope."])

        return (header, window_note, hero, overlay, overlay_note, feed, scorecard,
                corr, lag_table, forecast, meta)
