"""Balance & Composition tab (was "Summary Details / Balance Check").

Portfolio dollar-balance and record-count composition for Port 2025 over time,
broken down by 8 segmentation dimensions, for ANY snapshot pair. Reconciliation
is the lens: segments with abrupt count swings are flagged (`detect_count_anomalies`,
vendored below so this view stays self-contained), and a full-history
balance/count trend gives the two-quarter snapshot context.

The period selector is the tab's own state (SUMMARY_PRIOR_Q / SUMMARY_CURRENT_Q
in the HTML) and is NOT tied to the dashboard's Within/Cross comparison — Port
2024 has no balance-by-dimension data, so a Cross-Portfolio balance view is
impossible (frozen backend). Segments for the pair come from
`summary_by_quarter`; `summary_segments` provides only the dim metadata.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html
from plotly import graph_objects as go

from .common import (
    GRAPH_CFG, GRID2, P24_COLOR, P25_COLOR, SECTION, SECTION_IN_GRID,
    SECTION_TITLE, cmp_layout, empty_note, fig, fmt, fmt_n, help_tip, q_label,
    simple_table, td,
)

TAB = "summary_details"

BAL_CHANGE_HELP = (
    "Balance Change % = percent change in the segment's summed Balance from the "
    "prior period to the current period — (current Balance ÷ prior Balance − 1) "
    "× 100. The two periods are the snapshots named in the column headers."
)
ANOMALY_HELP = (
    "A segment is flagged when its record count crosses a structural threshold "
    "between the two snapshots: it appeared (0 → ≥10), disappeared (≥10 → 0), or "
    "changed ≥2× with a swing of ≥10 records. These usually signal a feed break "
    "or a re-mapping rather than real portfolio movement — reconcile them before "
    "trusting the balances for those buckets."
)
TREND_HELP = (
    "Total portfolio Balance (left axis) and record count (right axis) across "
    "every Port 2025 snapshot. The two diamonds mark the prior → current pair "
    "selected above, so you can see where this comparison sits in the history."
)


# Vendored verbatim from dq_wholesale/callbacks/segment_breakdowns.py so this
# view imports nothing from the backend — it only reads the metrics payload.
# Pure logic (dict in, list out). Keep the thresholds in sync if the backend's
# detect_count_anomalies ever changes.
def detect_count_anomalies(summary_segments, ratio_threshold=2.0, abs_min=10):
    """Flag segments with drastic record-count swings between the two periods:
    appeared (0 → >0) · disappeared (>0 → 0) · drastic_growth (≥ratio & ≥abs) ·
    drastic_drop (≤1/ratio & ≥abs). Sorted by |change| descending.
    """
    alerts = []
    for dim_key, entry in summary_segments.items():
        for row in entry.get("rows", []):
            p = int(row.get("prior_records", 0) or 0)
            c = int(row.get("records", 0) or 0)
            base = {
                "dim_key": dim_key,
                "dim_label": entry.get("label", dim_key),
                "dim_column": entry.get("column", ""),
                "segment": row["segment"],
                "prior": p, "current": c, "change": c - p,
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
    alerts.sort(key=lambda a: -abs(a["change"]))
    return alerts


def _default_pair(metrics):
    base = metrics.get("summary_segments") or {}
    first = next(iter(base.values()), {})
    return first.get("prior_q") or "", first.get("current_q") or ""


def _segments_for_pair(metrics, prior_q, current_q):
    """Port of _segmentsForPair — same shape as DASH_DATA.summary_segments."""
    base = metrics.get("summary_segments") or {}
    by_q = metrics.get("summary_by_quarter") or {}
    prv = by_q.get(prior_q) or {}
    cur = by_q.get(current_q) or {}
    out = {}
    for dim_key, meta in base.items():
        prv_segs = (prv.get(dim_key) or {}).get("segments") or {}
        cur_segs = (cur.get(dim_key) or {}).get("segments") or {}
        rows = []
        for seg in sorted(set(prv_segs) | set(cur_segs)):
            p = prv_segs.get(seg) or {"count": 0, "balance": 0}
            c = cur_segs.get(seg) or {"count": 0, "balance": 0}
            p_bal, c_bal = float(p.get("balance") or 0), float(c.get("balance") or 0)
            ratio = (round(c_bal / p_bal * 100, 1) if abs(p_bal) > 1e-9 else None)
            rows.append({
                "segment": seg,
                "records": int(c.get("count") or 0),
                "prior_records": int(p.get("count") or 0),
                "record_change": int(c.get("count") or 0) - int(p.get("count") or 0),
                "current_balance": round(c_bal, 2),
                "prior_balance": round(p_bal, 2),
                "ratio_pct": ratio,
            })
        out[dim_key] = {"label": meta.get("label"), "column": meta.get("column"),
                        "current_q": current_q, "prior_q": prior_q, "rows": rows}
    return out


def _portfolio_totals(segs):
    """Portfolio-wide count/balance totals from the first dimension's rows
    (every dimension covers the same population, so any one totals correctly)."""
    keys = list(segs)
    rows = ((segs[keys[0]] or {}).get("rows") or []) if keys else []
    cur_total = sum(float(r.get("current_balance") or 0) for r in rows)
    prv_total = sum(float(r.get("prior_balance") or 0) for r in rows)
    cur_count = sum(int(r.get("records") or 0) for r in rows)
    prv_count = sum(int(r.get("prior_records") or 0) for r in rows)
    change = ((cur_total - prv_total) / prv_total * 100
              if abs(prv_total) > 1e-9 else None)
    cnt_change = ((cur_count - prv_count) / prv_count * 100 if prv_count > 0 else None)
    return {"cur_total": cur_total, "prv_total": prv_total, "cur_count": cur_count,
            "prv_count": prv_count, "change": change, "cnt_change": cnt_change}


def _fmt_balance(v):
    if v is None:
        return "—"
    v = float(v)
    if abs(v) < 1e-9:
        return "$0"
    sign = "-" if v < 0 else ""
    return f"{sign}${fmt_n(round(abs(v)))}"


def _fmt_change(change):
    if change is None:
        return "—"
    sign = "+" if change > 0 else ("-" if change < 0 else "")
    return f"{sign}{fmt(abs(change), 1)}%"


def _change_color(change):
    if change is None:
        return "#94a3b8"
    if change > 100:
        return "#15803d"
    if change >= 10:
        return "#16a34a"
    if change <= -50:
        return "#7f1d1d"
    if change <= -10:
        return "#dc2626"
    return "#475569"


def _count_cell_color(r):
    p, c = int(r.get("prior_records") or 0), int(r.get("records") or 0)
    if p == 0 and c >= 10:
        return "#15803d"
    if c == 0 and p >= 10:
        return "#991b1b"
    if p > 0 and c > 0:
        ratio = c / p
        if ratio >= 2.0 and (c - p) >= 10:
            return "#15803d"
        if ratio <= 0.5 and (p - c) >= 10:
            return "#991b1b"
    return "#475569"


def _dot(color, size=10):
    return html.Span(style={"width": f"{size}px", "height": f"{size}px",
                            "borderRadius": "50%", "background": color,
                            "display": "inline-block", "flex": "0 0 auto"})


# kind → tone/label (emoji removed; a colored dot + label carries the meaning).
KIND_META = {
    "appeared":       {"tone": "#15803d", "bg": "#dcfce7", "label": "Appeared"},
    "disappeared":    {"tone": "#991b1b", "bg": "#fee2e2", "label": "Disappeared"},
    "drastic_growth": {"tone": "#15803d", "bg": "#dcfce7", "label": "Drastic growth"},
    "drastic_drop":   {"tone": "#991b1b", "bg": "#fee2e2", "label": "Drastic drop"},
}


def _anomaly_panel(anomalies, cur_label, prv_label):
    if not anomalies:
        return html.Div([
            _dot("#16a34a"),
            html.Div([
                html.Div("No drastic record-count swings detected",
                         style={"fontSize": "12px", "fontWeight": "700",
                                "color": "#15803d"}),
                html.Div(f"All segments retain comparable record counts between "
                         f"{prv_label} and {cur_label}. Thresholds: 2× ratio or "
                         f"≥10 records appeared/disappeared.",
                         style={"fontSize": "11px", "color": "#166534"}),
            ]),
        ], style={"background": "#f0fdf4", "border": "1px solid #bbf7d0",
                  "borderRadius": "8px", "padding": "12px 14px",
                  "marginBottom": "14px", "display": "flex", "alignItems": "center",
                  "gap": "10px"})

    by_dim = {}
    for a in anomalies:
        by_dim.setdefault(a["dim_key"], {"label": a["dim_label"],
                                         "column": a["dim_column"], "rows": []})
        by_dim[a["dim_key"]]["rows"].append(a)

    dim_blocks = []
    for group in by_dim.values():
        row_els = []
        for a in group["rows"]:
            meta = KIND_META.get(a["kind"], KIND_META["disappeared"])
            change = a["change"]
            ratio = (f"{fmt(a['current'] / a['prior'] * 100, 0)}%"
                     if a["prior"] > 0 and a["current"] > 0
                     else ("∞" if a["prior"] == 0 else "0"))
            row_els.append(html.Div([
                _dot(meta["tone"], 8),
                html.Div([
                    html.Span(a["segment"], style={"fontFamily": "monospace",
                                                   "fontWeight": "700",
                                                   "color": "#0f172a"}),
                    html.Span(meta["label"], style={"fontSize": "11px",
                                                    "color": meta["tone"],
                                                    "fontWeight": "600",
                                                    "margin": "0 8px"}),
                    html.Span([f"{prv_label}: ", html.Strong(fmt_n(a["prior"])),
                               f" → {cur_label}: ", html.Strong(fmt_n(a["current"]))],
                              style={"fontSize": "11px", "color": "#475569",
                                     "fontFamily": "monospace"}),
                ], style={"flex": "1"}),
                html.Span(f"{'+' if change > 0 else ''}{fmt_n(change)} · ratio {ratio}",
                          style={"fontSize": "11px", "fontWeight": "700",
                                 "color": meta["tone"], "fontFamily": "monospace"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                      "padding": "6px 10px", "background": meta["bg"],
                      "borderLeft": f"3px solid {meta['tone']}",
                      "borderRadius": "0 4px 4px 0", "marginBottom": "6px"}))
        dim_blocks.append(html.Div([
            html.Div([
                html.Div(group["label"], style={"fontSize": "12px", "fontWeight": "700",
                                                "color": "#0f172a"}),
                html.Div(f"{len(group['rows'])} flagged · grouped by {group['column']}",
                         style={"fontSize": "10px", "color": "#64748b",
                                "fontFamily": "monospace"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "baseline", "marginBottom": "8px"}),
            html.Div(row_els),
        ], style={"background": "#fff", "border": "1px solid #e2e8f0",
                  "borderRadius": "8px", "padding": "12px 14px",
                  "marginBottom": "8px"}))

    total = len(anomalies)
    return html.Div([
        html.Div([
            _dot("#d97706", 14),
            html.Div([
                html.Div([f"Record-count anomalies between {prv_label} and {cur_label}",
                          help_tip(ANOMALY_HELP)],
                         style={"fontSize": "13px", "fontWeight": "700",
                                "color": "#92400e", "display": "flex",
                                "alignItems": "center"}),
                html.Div([html.Strong(str(total)),
                          f" segment{'s' if total != 1 else ''} flagged. Thresholds: "
                          "2× ratio (≥10 records) or any segment that appeared / "
                          "disappeared. Investigate before trusting the balances for "
                          "those buckets."],
                         style={"fontSize": "11px", "color": "#92400e",
                                "marginTop": "2px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "marginBottom": "10px"}),
        html.Div(dim_blocks),
    ], style={"background": "#fffbeb", "border": "1px solid #fcd34d",
              "borderLeft": "4px solid #d97706", "borderRadius": "8px",
              "padding": "14px 16px", "marginBottom": "14px"})


def _totals_strip(totals, cur_label, prv_label):
    def card(label, value, sub, accent, value_color="#0f172a"):
        return html.Div([
            html.Div(label, style={"fontSize": "10px", "color": "#64748b",
                                   "fontWeight": "700", "textTransform": "uppercase",
                                   "letterSpacing": ".05em"}),
            html.Div(value, style={"fontSize": "22px", "fontWeight": "800",
                                   "color": value_color, "lineHeight": "1",
                                   "marginTop": "6px"}),
            html.Div(sub, style={"fontSize": "10px", "marginTop": "4px",
                                 "color": "#64748b"}),
        ], style={"background": "#fff", "border": "1px solid #e2e8f0",
                  "borderLeft": f"4px solid {accent}", "borderRadius": "8px",
                  "padding": "14px"})

    cnt_c = _change_color(totals["cnt_change"])
    chg_c = _change_color(totals["change"])
    return html.Div([
        card(f"Count · {prv_label}", fmt_n(totals["prv_count"]),
             "facilities · prior period", "#2563eb"),
        card(f"Count · {cur_label}", fmt_n(totals["cur_count"]),
             html.Span(f"{_fmt_change(totals['cnt_change'])} vs {prv_label}",
                       style={"color": cnt_c}), cnt_c),
        card(f"Portfolio Balance · {prv_label}", _fmt_balance(totals["prv_total"]),
             "prior period reference", "#2563eb"),
        card(f"Portfolio Balance · {cur_label}", _fmt_balance(totals["cur_total"]),
             "sum of Balance column · current period", "#16a34a"),
        card("Overall Balance Change", _fmt_change(totals["change"]),
             f"portfolio-wide change vs {prv_label}", chg_c, value_color=chg_c),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(5, 1fr)",
              "gap": "12px", "marginBottom": "14px"})


def _portfolio_trend(metrics):
    """Total balance + count per snapshot across the full Port 2025 history."""
    sbq = metrics.get("summary_by_quarter") or {}
    base = metrics.get("summary_segments") or {}
    dim = next(iter(base), None)
    out = []
    for q in sorted(sbq):
        segs = ((sbq[q] or {}).get(dim) or {}).get("segments") or {}
        out.append({
            "quarter": q,
            "balance": sum(float(v.get("balance") or 0) for v in segs.values()),
            "count": sum(int(v.get("count") or 0) for v in segs.values()),
        })
    return out


def _trend_section(metrics, prior_q, current_q):
    data = _portfolio_trend(metrics)
    if not data:
        return empty_note("No history available for the portfolio trend.")
    x = [q_label(d["quarter"]) for d in data]
    bal = [d["balance"] for d in data]
    cnt = [d["count"] for d in data]
    traces = [
        go.Scatter(x=x, y=bal, name="Portfolio Balance", mode="lines",
                   line={"color": P25_COLOR, "width": 2}, connectgaps=True),
        go.Scatter(x=x, y=cnt, name="Record Count", mode="lines", yaxis="y2",
                   line={"color": P24_COLOR, "width": 1.5, "dash": "dot"},
                   connectgaps=True),
    ]
    by_label = {q_label(d["quarter"]): d["balance"] for d in data}
    sel = [(q_label(prior_q), by_label.get(q_label(prior_q))),
           (q_label(current_q), by_label.get(q_label(current_q)))]
    sel = [(ql, y) for ql, y in sel if y is not None]
    if sel:
        traces.append(go.Scatter(
            x=[s[0] for s in sel], y=[s[1] for s in sel], name="Selected pair",
            mode="markers", marker={"size": 11, "color": "#0f172a",
                                    "symbol": "diamond"}))
    layout = cmp_layout("Balance ($)", height=240, x_title="Quarter")
    layout["margin"]["r"] = 58
    layout["yaxis2"] = {"title": {"text": "Records", "font": {"size": 10}},
                        "overlaying": "y", "side": "right", "showgrid": False,
                        "tickfont": {"size": 9}}
    return dcc.Graph(figure=fig(traces, layout), config=GRAPH_CFG)


def _dim_card(entry, cur_label, prv_label):
    rows = entry.get("rows") or []
    if not rows:
        return html.Div([
            html.Div(entry.get("label"), style=SECTION_TITLE),
            html.Div("No segments for this dimension.",
                     style={"padding": "24px", "color": "#94a3b8", "fontSize": "12px",
                            "textAlign": "center"}),
        ], style=SECTION_IN_GRID)

    tot_c = sum(float(r.get("current_balance") or 0) for r in rows)
    tot_p = sum(float(r.get("prior_balance") or 0) for r in rows)
    tot_rc = sum(int(r.get("records") or 0) for r in rows)
    tot_rp = sum(int(r.get("prior_records") or 0) for r in rows)
    tot_change = ((tot_c - tot_p) / tot_p * 100 if abs(tot_p) > 1e-9 else None)

    body = []
    for r in rows:
        cnt_color = _count_cell_color(r)
        is_anom = cnt_color != "#475569"
        bal_change = (r["ratio_pct"] - 100) if r.get("ratio_pct") is not None else None
        seg_label = [str(r.get("segment"))]
        if is_anom:
            seg_label.append(html.Span(" ", style={"display": "inline"}))
            seg_label.append(_dot("#d97706", 7))
        body.append(html.Tr([
            td(seg_label, fontWeight="600", color="#0f172a"),
            td(fmt_n(r.get("prior_records") or 0), textAlign="right",
               fontFamily="monospace", color="#475569"),
            td(fmt_n(r.get("records") or 0), textAlign="right",
               fontFamily="monospace", color=cnt_color,
               fontWeight="700" if is_anom else "500"),
            td(_fmt_balance(r.get("prior_balance")), textAlign="right",
               fontFamily="monospace",
               color="#dc2626" if (r.get("prior_balance") or 0) < 0 else "#475569"),
            td(_fmt_balance(r.get("current_balance")), textAlign="right",
               fontFamily="monospace",
               color="#dc2626" if (r.get("current_balance") or 0) < 0 else "#0f172a"),
            td(_fmt_change(bal_change), textAlign="right", fontWeight="600",
               color=_change_color(bal_change)),
        ], style={"background": "#fffbeb"} if is_anom else None))

    body.append(html.Tr([
        td("TOTAL", fontWeight="700", color="#0f1d35"),
        td(fmt_n(tot_rp), textAlign="right", fontFamily="monospace", fontWeight="700"),
        td(fmt_n(tot_rc), textAlign="right", fontFamily="monospace", fontWeight="700"),
        td(_fmt_balance(tot_p), textAlign="right", fontFamily="monospace",
           fontWeight="700"),
        td(_fmt_balance(tot_c), textAlign="right", fontFamily="monospace",
           fontWeight="700"),
        td(_fmt_change(tot_change), textAlign="right", fontWeight="700",
           color=_change_color(tot_change)),
    ], style={"background": "#f8fafc", "borderTop": "2px solid #0f1d35"}))

    dark = {"background": "#1e293b", "color": "#fff", "textAlign": "right"}
    headers = [entry.get("label"), f"Count · {prv_label}", f"Count · {cur_label}",
               f"{prv_label} Balance", f"{cur_label} Balance",
               html.Span(["Balance Change %",
                          help_tip(BAL_CHANGE_HELP, "#3b82f6", align="end")])]
    header_styles = [{"background": "#0f1d35", "color": "#fff"},
                     dark, dark, dark, dark, dark]

    return html.Div([
        html.Div(entry.get("label"), style=dict(SECTION_TITLE, marginBottom="10px")),
        html.Div(simple_table(headers, body, header_styles=header_styles),
                 style={"overflowX": "auto"}),
    ], style=SECTION_IN_GRID)


def layout(metrics: dict):
    quarters = metrics.get("quarters") or []
    def_prior, def_current = _default_pair(metrics)
    q_opts = [{"label": q_label(q), "value": q} for q in reversed(quarters)]

    return [
        html.Div([
            html.H2("Balance & Composition",
                    style={"margin": "0 0 6px", "fontSize": "20px"}),
            html.P(id=f"dqd-{TAB}-subtitle",
                   style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
        ], style=SECTION),

        html.Div([
            html.Span("COMPARISON PERIOD", style={"fontSize": "10px",
                                                  "fontWeight": "700",
                                                  "color": "#64748b",
                                                  "letterSpacing": ".05em"}),
            html.Span("Prior", style={"fontSize": "11px", "color": "#64748b",
                                      "marginLeft": "12px"}),
            dcc.Dropdown(id=f"dqd-{TAB}-prior-q", options=q_opts, value=def_prior,
                         clearable=False,
                         style={"width": "150px", "fontSize": "11px"}),
            html.Span("→ Current", style={"fontSize": "11px", "color": "#64748b"}),
            dcc.Dropdown(id=f"dqd-{TAB}-current-q", options=q_opts, value=def_current,
                         clearable=False,
                         style={"width": "150px", "fontSize": "11px"}),
            html.Button("↺ Reset to default YE pair", id=f"dqd-{TAB}-reset", n_clicks=0,
                        style={"fontSize": "10px", "padding": "4px 12px",
                               "border": "1px solid #cbd5e1", "background": "#fff",
                               "color": "#475569", "borderRadius": "4px",
                               "cursor": "pointer"}),
            html.Span(id=f"dqd-{TAB}-pair-echo",
                      style={"marginLeft": "auto", "fontSize": "11px",
                             "color": "#475569", "fontFamily": "monospace"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "flexWrap": "wrap", "padding": "10px 14px",
                  "background": "#f8fafc", "border": "1px solid #e2e8f0",
                  "borderRadius": "8px", "marginBottom": "14px"}),

        html.Div(id=f"dqd-{TAB}-anomalies"),
        html.Div(id=f"dqd-{TAB}-totals"),

        html.Div([
            html.Div(["Portfolio Balance & Record Count — full history",
                      help_tip(TREND_HELP)],
                     style=dict(SECTION_TITLE, display="flex", alignItems="center")),
            html.Div(id=f"dqd-{TAB}-trend"),
        ], style=SECTION),

        html.Div(["Detailed breakdown by dimension",
                  html.Span(" · prior vs current balance and record count per "
                            "segment; flagged segments tinted",
                            style={"fontSize": "10px", "fontWeight": "500",
                                   "color": "#94a3b8", "textTransform": "none",
                                   "letterSpacing": "normal"})],
                 style={"fontSize": "12px", "fontWeight": "700", "color": "#0f172a",
                        "textTransform": "uppercase", "letterSpacing": ".05em",
                        "margin": "4px 0 10px", "paddingTop": "14px",
                        "borderTop": "1px solid #e2e8f0"}),
        html.Div(id=f"dqd-{TAB}-cards", style=GRID2),
    ]


def register_callbacks(app, metrics: dict):
    def_prior, def_current = _default_pair(metrics)

    @app.callback(
        Output(f"dqd-{TAB}-prior-q", "value"),
        Output(f"dqd-{TAB}-current-q", "value"),
        Input(f"dqd-{TAB}-reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset(_n):
        return def_prior, def_current

    @app.callback(
        Output(f"dqd-{TAB}-subtitle", "children"),
        Output(f"dqd-{TAB}-pair-echo", "children"),
        Output(f"dqd-{TAB}-anomalies", "children"),
        Output(f"dqd-{TAB}-totals", "children"),
        Output(f"dqd-{TAB}-trend", "children"),
        Output(f"dqd-{TAB}-cards", "children"),
        Input(f"dqd-{TAB}-prior-q", "value"),
        Input(f"dqd-{TAB}-current-q", "value"),
    )
    def _update(prior_q, current_q):
        prior_q = prior_q or def_prior
        current_q = current_q or def_current
        prv_label = q_label(prior_q) or "—"
        cur_label = q_label(current_q) or "—"

        segs = _segments_for_pair(metrics, prior_q, current_q)
        anomalies = detect_count_anomalies(segs)
        totals = _portfolio_totals(segs)

        subtitle = html.Span([
            "Portfolio dollar balance and record-count composition by segmentation "
            "dimension, for Port 2025 over time. Current pair: ",
            html.Strong(prv_label), " → ", html.Strong(cur_label),
            ". Pick any snapshot pair to reconcile; segments with abrupt count "
            "swings are flagged below."])
        echo = html.Span([html.Strong(prv_label), " → ", html.Strong(cur_label),
                          ("  (default year-end pair)"
                           if (prior_q, current_q) == (def_prior, def_current) else "")])
        cards = [_dim_card(segs[k], cur_label, prv_label) for k in segs]
        return (subtitle, echo,
                _anomaly_panel(anomalies, cur_label, prv_label),
                _totals_strip(totals, cur_label, prv_label),
                _trend_section(metrics, prior_q, current_q),
                cards)
