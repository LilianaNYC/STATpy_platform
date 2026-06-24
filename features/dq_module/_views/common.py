"""Shared helpers for the Dash-native DQ dashboard.

Python ports of the HTML dashboard's shared JS:
  - helpers_js.py formatters (pct / fmt / fmtN / fmtB / qLabel / spark / badge)
  - comparison_mode.py slicing (_cmpFilter / _cmpX / _cmpTraces / _cmpLayout)
  - the styling constants proven in `dashboards/Dash app Dashboard test/app.py`

Every component ID in the app is prefixed `dqd-<tab>-…` (STATpy-safe
namespacing, same idea as `dashboards-<key>-…` in dashboards_callbacks.py).
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

# ── Palette ───────────────────────────────────────────────────────────────

P24_COLOR = "#2563eb"   # Port 2024 — blue
P25_COLOR = "#16a34a"   # Port 2025 — green

STATUS = {
    "green": {"dot": "#16a34a", "bg": "#dcfce7"},
    "amber": {"dot": "#d97706", "bg": "#fef3c7"},
    "red":   {"dot": "#dc2626", "bg": "#fee2e2"},
    "gray":  {"dot": "#6b7280", "bg": "#f3f4f6"},
}

SEV_COLORS = {
    "Critical": "#dc2626",
    "High":     "#ea580c",
    "Medium":   "#d97706",
    "Low":      "#65a30d",
    "Very Low": "#16a34a",
}

# badge() class map from helpers_js.py, flattened to colors
BADGE_COLORS = {
    "Critical": ("#fee2e2", "#991b1b"),
    "High":     ("#ffedd5", "#9a3412"),
    "Medium":   ("#fef3c7", "#92400e"),
    "Low":      ("#ecfccb", "#3f6212"),
    "Very Low": ("#dcfce7", "#166534"),
    "Open":     ("#fee2e2", "#991b1b"),
    "In Progress": ("#fef3c7", "#92400e"),
    "Resolved": ("#dcfce7", "#166534"),
    "Stable":   ("#dcfce7", "#166534"),
    "Elevated": ("#fef3c7", "#92400e"),
    "GREEN":    ("#dcfce7", "#166534"),
    "MODERATE": ("#fef3c7", "#92400e"),
    "RED":      ("#fee2e2", "#991b1b"),
    "No Drift": ("#dcfce7", "#166534"),
    "Minor":    ("#ecfccb", "#3f6212"),
    "Moderate": ("#fef3c7", "#92400e"),
    "Significant": ("#fee2e2", "#991b1b"),
}

# ── Layout styles ─────────────────────────────────────────────────────────

SECTION = {
    "background": "#fff", "border": "1px solid #e2e8f0", "borderRadius": "10px",
    "padding": "16px", "marginBottom": "16px",
    "boxShadow": "0 1px 2px rgba(15,23,42,.04)",
}
SECTION_IN_GRID = dict(SECTION, marginBottom="0", minWidth="0")
SECTION_TITLE = {
    "fontSize": "11px", "fontWeight": "700", "letterSpacing": ".06em",
    "textTransform": "uppercase", "color": "#64748b", "marginBottom": "8px",
}
CARD = {"background": "#fff", "border": "1px solid #e2e8f0",
        "borderRadius": "10px", "padding": "14px"}
MUTED = {"fontSize": "11px", "color": "#64748b"}
GRAPH_CFG = {"responsive": True, "displayModeBar": False}

GRID2 = {"display": "grid", "gridTemplateColumns": "repeat(2, 1fr)",
         "gap": "12px", "marginBottom": "16px"}
GRID3 = {"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
         "gap": "12px", "marginBottom": "16px"}

TABLE_CELL = {"fontSize": "11px", "padding": "5px 8px",
              "borderBottom": "1px solid #f1f5f9", "textAlign": "left"}
TABLE_HEADER = {"fontSize": "10px", "fontWeight": "700", "textTransform": "uppercase",
                "color": "#64748b", "background": "#f8fafc", "padding": "6px 8px",
                "textAlign": "left"}


# ── Formatters (ports of helpers_js) ─────────────────────────────────────

def fmt(v, d: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{d}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_n(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(round(float(v))):,}"
    except (TypeError, ValueError):
        return "—"


def fmt_b(v) -> str:
    return "—" if v is None else f"${fmt(v, 3)}B"


def pct(v, d: int = 1) -> str:
    return "—" if v is None else f"{fmt(v, d)}%"


def q_label(q) -> str:
    q = str(q or "")
    return f"{q[:4]} Q{q[5:]}" if len(q) >= 6 else q


def spark(vals) -> str:
    """Unicode sparkline, same glyphs as helpers_js spark()."""
    vals = [v for v in (vals or []) if v is not None]
    if not vals:
        return "—"
    lo, hi = min(vals), max(vals)
    bars = "▁▂▃▄▅▆▇█"
    rng = (hi - lo) + 1e-9
    return "".join(bars[int(round((v - lo) / rng * (len(bars) - 1)))] for v in vals)


def badge(label) -> html.Span:
    bg, fg = BADGE_COLORS.get(str(label), ("#f3f4f6", "#374151"))
    return html.Span(str(label if label is not None else "—"), style={
        "display": "inline-block", "fontSize": "10px", "fontWeight": "700",
        "background": bg, "color": fg, "padding": "2px 8px", "borderRadius": "10px",
    })


def arrow_delta(d, good_when_up: bool = True, d_digits: int = 2):
    """Port of helpers_js arrow(): colored ▲/▼ with the |delta|."""
    if d is None or d == 0:
        return html.Span("—", style={"color": "#6b7280"})
    good = (d > 0) == good_when_up
    color = "#16a34a" if good else "#dc2626"
    sym = "▲" if d > 0 else "▼"
    return html.Span(f"{sym} {fmt(abs(d), d_digits)}",
                     style={"color": color, "fontWeight": "600"})


# ── Small component builders ──────────────────────────────────────────────

def section(title, *children, style=None, title_extra=None):
    head = [title] if title_extra is None else [title, " ", title_extra]
    return html.Div([html.Div(head, style=SECTION_TITLE), *children],
                    style=style or SECTION)


def kpi_card(label, value, sub: str = "", color: str = "#0f172a", icon: str = "",
             delta=None, accent=None):
    style = dict(CARD)
    if accent:
        style["borderLeft"] = f"4px solid {accent}"
    kids = []
    if icon:
        kids.append(html.Div(icon, style={"fontSize": "15px"}))
    kids += [
        html.Div(label, style={"fontSize": "10px", "fontWeight": "700",
                               "letterSpacing": ".05em", "textTransform": "uppercase",
                               "color": "#64748b"}),
        html.Div(value, style={"fontSize": "21px", "fontWeight": "700",
                               "color": color, "margin": "4px 0 2px"}),
        html.Div(sub, style={"fontSize": "11px", "color": "#94a3b8"}),
    ]
    if delta is not None:
        kids.append(html.Div(delta, style={"fontSize": "11px", "marginTop": "2px"}))
    return html.Div(kids, style=style)


def kpi_grid(cards, cols: int):
    return html.Div(cards, style={"display": "grid",
                                  "gridTemplateColumns": f"repeat({cols}, 1fr)",
                                  "gap": "12px", "marginBottom": "14px"})


def simple_table(headers, body_rows, font_size: str = "11px", header_styles=None):
    """headers: list of str/components (or (text, style) tuples);
    body_rows: list of html.Tr."""
    ths = []
    for i, h in enumerate(headers):
        st = dict(TABLE_HEADER)
        if header_styles and i < len(header_styles) and header_styles[i]:
            st.update(header_styles[i])
        ths.append(html.Th(h, style=st))
    return html.Table(
        [html.Thead(html.Tr(ths)), html.Tbody(body_rows)],
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": font_size})


def td(content, **style):
    st = dict(TABLE_CELL)
    st.update(style)
    return html.Td(content, style=st)


def empty_note(text):
    return html.Div(text, style={"padding": "16px", "color": "#94a3b8",
                                 "fontSize": "12px", "textAlign": "center"})


def help_tip(text: str, color: str = "#94a3b8", align: str = "start") -> html.Span:
    """A small circular '?' badge that reveals a styled tooltip bubble on hover.

    Zero-callback and accessible. The bubble is pure CSS (`.dqd-help*` classes
    injected in app.py's index_string) and appears on hover after a short delay
    (`--dqd-help-delay`). Deliberately does NOT set the native title= attribute
    — that would surface a second, slower OS tooltip on top of this one. The
    accessible name is carried by aria-label (screen-reader only, not visible).
    Place inline right after a label/metric.

    align="end" right-anchors the bubble (extends leftward) — use it for tips
    inside an overflow-x container near its right edge (e.g. a last table
    column) so the bubble doesn't get clipped.
    """
    cls = "dqd-help dqd-help--end" if align == "end" else "dqd-help"
    return html.Span(
        [html.Span("?", className="dqd-help__b",
                   style={"marginLeft": "5px", "background": color}),
         html.Span(text, className="dqd-help__t")],
        className=cls, **{"aria-label": text})


# ── Comparison-mode slicing (ports of comparison_mode.py) ─────────────────

def cmp_filter(arr, mode, hist_start=None, hist_end=None):
    """Port of _cmpFilter. YoY uses each series' own latest year (the HTML
    default when no year override is picked)."""
    arr = arr or []
    if mode == "qoq":
        return arr[-12:]
    if mode == "yoy":
        if not arr:
            return arr
        yr = max(int(str(r["quarter"])[:4]) for r in arr)
        return [r for r in arr if int(str(r["quarter"])[:4]) == yr]
    if hist_start or hist_end:
        return [r for r in arr
                if (not hist_start or str(r["quarter"]) >= hist_start)
                and (not hist_end or str(r["quarter"]) <= hist_end)]
    return arr


def cmp_x(arr, mode):
    if mode == "yoy":
        return ["Q" + str(r["quarter"])[5:] for r in arr]
    return [r.get("label") or q_label(r.get("quarter")) for r in arr]


def line_trace(x, y, name, color, dash=None):
    return go.Scatter(x=x, y=y, name=name, mode="lines+markers",
                      line={"color": color, "width": 2, "dash": dash or "solid"},
                      marker={"size": 3, "color": color}, connectgaps=True)


def cmp_traces(metrics, ts_key, y_key, mode, hist_start=None, hist_end=None,
               name24="Port 2024", name25="Port 2025",
               color24=P24_COLOR, color25=P25_COLOR):
    """Port of _cmpTraces: Port 2024 overlay in YoY/Historical, Port 2025 always."""
    ts25 = (metrics.get("time_series") or {}).get(ts_key) or []
    ts24 = ((metrics.get("port24") or {}).get("time_series") or {}).get(ts_key) or []
    a25 = cmp_filter(ts25, mode, hist_start, hist_end)
    a24 = cmp_filter(ts24, mode, hist_start, hist_end)
    traces = []
    if mode != "qoq" and a24:
        lbl24 = name24
        if mode == "yoy" and a24:
            lbl24 = f"Port 2024 ({str(a24[0]['quarter'])[:4]})"
        traces.append(line_trace(cmp_x(a24, mode), [r.get(y_key) for r in a24],
                                 lbl24, color24))
    lbl25 = name25
    if mode == "yoy" and a25:
        lbl25 = f"Port 2025 ({str(a25[0]['quarter'])[:4]})"
    traces.append(line_trace(cmp_x(a25, mode), [r.get(y_key) for r in a25],
                             lbl25, color25))
    return traces


def cmp_layout(y_title, height: int = 180, showlegend: bool = True,
               x_title=None, **yaxis_extra):
    yaxis = {"title": y_title, "gridcolor": "#f1f5f9", "tickfont": {"size": 9}}
    yaxis.update(yaxis_extra)
    xaxis = {"showgrid": False, "tickfont": {"size": 8}, "tickangle": -45}
    if x_title:
        xaxis["title"] = {"text": x_title, "font": {"size": 10}}
    return {
        "margin": {"t": 10, "r": 10, "b": 50, "l": 55}, "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "xaxis": xaxis,
        "yaxis": yaxis,
        "legend": {"orientation": "h", "y": 1.18, "x": 0, "font": {"size": 9}},
        "showlegend": showlegend,
    }


def fig(traces, layout) -> go.Figure:
    f = go.Figure(traces)
    f.update_layout(**layout)
    return f


# ── Mode bar (shared CMP_MODE control surface) ────────────────────────────
#
# Each tab gets its own mode state (the HTML keeps one global CMP_MODE; in
# Dash per-tab stores avoid cross-tab callback fan-out). IDs:
#   dqd-<tab>-cmp-mode / -cq / -pq / -hist-start / -hist-end

def mode_bar(tab: str, metrics: dict, default_mode: str = "historical"):
    quarters = metrics.get("quarters") or []
    cq = metrics.get("latest_quarter")
    pq = metrics.get("prior_quarter")
    q24 = (metrics.get("port24") or {}).get("quarters") or []
    q_opts = [{"label": q_label(q), "value": q} for q in reversed(quarters)]
    q_opts_asc = [{"label": q_label(q), "value": q} for q in quarters]
    dd_style = {"width": "150px", "fontSize": "11px", "display": "inline-block"}
    lab = {"fontSize": "11px", "color": "#64748b", "margin": "0 4px 0 10px"}

    yoy_caption = (f"Cross-portfolio: fixed pair — P24 {q_label(q24[-1] if q24 else '')} → "
                   f"P25 {q_label(quarters[-1] if quarters else '')}")

    return html.Div([
        html.Div([
            html.Span("COMPARISON MODE:", style={"fontSize": "11px", "fontWeight": "700",
                                                 "color": "#64748b", "marginRight": "12px",
                                                 "letterSpacing": ".05em"}),
            dcc.RadioItems(
                id=f"dqd-{tab}-cmp-mode",
                options=[{"label": "QoQ — Same Portfolio", "value": "qoq"},
                         {"label": "YoY — Port 2024 vs Port 2025 (latest year each)",
                          "value": "yoy"},
                         {"label": "Historical Comparison", "value": "historical"}],
                value=default_mode, inline=True,
                labelStyle={"marginRight": "18px", "fontSize": "12px"},
                style={"display": "inline-block"}),
        ]),
        # QoQ pair row
        html.Div([
            html.Span("Baseline", style=lab),
            dcc.Dropdown(id=f"dqd-{tab}-pq", options=q_opts, value=pq,
                         clearable=False, style=dd_style),
            html.Span("→ Current", style=lab),
            dcc.Dropdown(id=f"dqd-{tab}-cq", options=q_opts, value=cq,
                         clearable=False, style=dd_style),
        ], id=f"dqd-{tab}-qoq-row",
            style={"display": "flex", "alignItems": "center", "marginTop": "8px"}),
        # Historical range row
        html.Div([
            html.Span("From", style=lab),
            dcc.Dropdown(id=f"dqd-{tab}-hist-start", options=q_opts_asc,
                         value=quarters[0] if quarters else None,
                         clearable=False, style=dd_style),
            html.Span("→ To", style=lab),
            dcc.Dropdown(id=f"dqd-{tab}-hist-end", options=q_opts_asc,
                         value=quarters[-1] if quarters else None,
                         clearable=False, style=dd_style),
        ], id=f"dqd-{tab}-hist-row",
            style={"display": "flex", "alignItems": "center", "marginTop": "8px"}),
        # YoY fixed-pair caption
        html.Div(yoy_caption, id=f"dqd-{tab}-yoy-row",
                 style={"fontSize": "11px", "color": "#0f172a", "fontFamily": "monospace",
                        "marginTop": "8px"}),
    ], style=SECTION)


def register_mode_bar(app, tab: str):
    """Show only the active mode's parameter sub-row."""
    from dash import Input, Output

    @app.callback(
        Output(f"dqd-{tab}-qoq-row", "style"),
        Output(f"dqd-{tab}-hist-row", "style"),
        Output(f"dqd-{tab}-yoy-row", "style"),
        Input(f"dqd-{tab}-cmp-mode", "value"),
    )
    def _toggle(mode):
        row = {"display": "flex", "alignItems": "center", "marginTop": "8px"}
        hid = {"display": "none"}
        cap = {"fontSize": "11px", "color": "#0f172a", "fontFamily": "monospace",
               "marginTop": "8px"}
        if mode == "qoq":
            return row, hid, hid
        if mode == "historical":
            return hid, row, hid
        return hid, hid, cap


def mode_inputs(tab: str):
    """The 5 Inputs every mode-bar-driven callback consumes, in fixed order:
    (mode, cq, pq, hist_start, hist_end)."""
    from dash import Input
    return [Input(f"dqd-{tab}-cmp-mode", "value"),
            Input(f"dqd-{tab}-cq", "value"),
            Input(f"dqd-{tab}-pq", "value"),
            Input(f"dqd-{tab}-hist-start", "value"),
            Input(f"dqd-{tab}-hist-end", "value")]


def lens_label(metrics, mode, cq, pq, hist_start, hist_end) -> str:
    """Port of _lensChip text — echoes the active comparison pair."""
    quarters = metrics.get("quarters") or []
    if mode == "qoq":
        baseline = pq or (quarters[quarters.index(cq) - 1]
                          if cq in quarters and quarters.index(cq) > 0 else cq)
        return f"QoQ · {q_label(baseline)} → {q_label(cq)}"
    if mode == "yoy":
        q24 = (metrics.get("port24") or {}).get("quarters") or []
        return (f"YoY · P24 {q_label(q24[-1] if q24 else '')} → "
                f"P25 {q_label(quarters[-1] if quarters else '')}")
    return (f"Historical · {q_label(hist_start or (quarters[0] if quarters else ''))}"
            f" → {q_label(hist_end or (quarters[-1] if quarters else ''))}")


def lens_chip(text: str, mode: str) -> html.Span:
    bg = {"qoq": "#2563eb", "yoy": "#7c3aed"}.get(mode, "#0891b2")
    return html.Span(text, style={
        "display": "inline-block", "fontSize": "9px", "fontWeight": "700",
        "color": "#fff", "background": bg, "padding": "2px 8px",
        "borderRadius": "10px", "marginLeft": "10px", "textTransform": "none",
        "whiteSpace": "nowrap", "verticalAlign": "middle"})


# ── Question bar (drift-style explicit-question selector) ─────────────────
#
# Extracted from the Drift tab's selector block so question-driven tabs share
# one look. Layout-only: per-question desc/detail spans stay callback-driven.
# IDs: dqd-<tab>-question / -question-desc / -question-detail

def question_bar(tab: str, questions: list, default: str) -> html.Div:
    """questions: [{"value": "q1", "label": "…"}, …]"""
    return html.Div([
        html.Div([
            dcc.RadioItems(
                id=f"dqd-{tab}-question",
                options=[{"label": q["label"], "value": q["value"]}
                         for q in questions],
                value=default, inline=True,
                labelStyle={"marginRight": "18px", "fontSize": "12px",
                            "fontWeight": "600"}),
            html.Span(id=f"dqd-{tab}-question-desc",
                      style={"fontSize": "11px", "color": "#475569",
                             "fontWeight": "600"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px",
                  "flexWrap": "wrap", "marginBottom": "10px"}),
        html.Div(id=f"dqd-{tab}-question-detail",
                 style={"fontSize": "11px", "color": "#475569", "lineHeight": "1.45",
                        "paddingTop": "8px", "borderTop": "1px dashed #e2e8f0"}),
    ], style=SECTION)


def question_chip(label: str, rng: str, color: str = "#2563eb") -> html.Span:
    """Pill echoing the active question + its quarter range."""
    return html.Span(f"{label} · {rng}", style={
        "display": "inline-block", "fontSize": "10px", "fontWeight": "700",
        "color": "#fff", "background": color, "padding": "2px 10px",
        "borderRadius": "10px", "marginLeft": "10px", "whiteSpace": "nowrap",
        "verticalAlign": "middle"})


def quarter_pair_picker(tab: str, quarters: list, default_prior, default_current):
    """Prior → Current snapshot-pair dropdowns (mirrors the Summary Details
    PRIOR/CURRENT pattern). IDs: dqd-<tab>-prior-q / -current-q."""
    q_opts = [{"label": q_label(q), "value": q} for q in reversed(quarters or [])]
    dd_style = {"width": "150px", "fontSize": "11px", "display": "inline-block"}
    lab = {"fontSize": "11px", "color": "#64748b", "margin": "0 4px 0 10px"}
    return html.Div([
        html.Span("Prior snapshot", style=dict(lab, marginLeft="0")),
        dcc.Dropdown(id=f"dqd-{tab}-prior-q", options=q_opts, value=default_prior,
                     clearable=False, style=dd_style),
        html.Span("→ Current", style=lab),
        dcc.Dropdown(id=f"dqd-{tab}-current-q", options=q_opts, value=default_current,
                     clearable=False, style=dd_style),
    ], style={"display": "flex", "alignItems": "center"})


# ── Shared sticky comparison + filter bar ─────────────────────────────────
# One consistent, pinned bar across Completeness / Population / Drift so the
# active comparison and filter stay visible while scrolling. Each tab keeps its
# own comparison logic and filters; these helpers unify look, placement and the
# deferred-apply controls.

STICKY_BAR = {
    "position": "sticky", "top": "0", "zIndex": 30,
    "background": "#ffffff", "border": "1px solid #e2e8f0",
    "borderRadius": "8px", "boxShadow": "0 2px 8px rgba(15,23,42,0.06)",
    "padding": "10px 14px", "margin": "0 0 16px",
}

# Within/Cross-Portfolio radio styling — reused by every tab's selector so the
# comparison toggle looks identical everywhere (values stay tab-specific).
COMPARE_LABEL_STYLE = {"marginRight": "16px", "fontSize": "12px",
                       "fontWeight": "700", "cursor": "pointer"}
COMPARE_INPUT_STYLE = {"marginRight": "5px"}


def compare_selector(tab, within_label="Within-Portfolio",
                     cross_label="Cross-Portfolio", default="within"):
    """Live Within/Cross-Portfolio toggle. Id: dqd-<tab>-compare."""
    return dcc.RadioItems(
        id=f"dqd-{tab}-compare",
        options=[{"label": within_label, "value": "within"},
                 {"label": cross_label, "value": "cross"}],
        value=default, inline=True,
        labelStyle=COMPARE_LABEL_STYLE, inputStyle=COMPARE_INPUT_STYLE)


def apply_filter_controls(tab, has_filter=True):
    """Right-aligned cluster: Apply button + active-filter chip + Clear button.
    Ids: dqd-<tab>-apply, -active-chip, -clear. has_filter=False drops the
    buttons (for tabs whose controls aren't deferrable filters, e.g. Drift)."""
    btn = {"fontSize": "11px", "fontWeight": "700", "padding": "5px 12px",
           "borderRadius": "6px", "cursor": "pointer"}
    kids = [html.Span(id=f"dqd-{tab}-active-chip")]
    if has_filter:
        kids = [
            html.Button("Apply filter", id=f"dqd-{tab}-apply", n_clicks=0,
                        style=dict(btn, background="#0f1d35", color="#fff",
                                   border="1px solid #0f1d35")),
            html.Span(id=f"dqd-{tab}-active-chip"),
            html.Button("Clear filter", id=f"dqd-{tab}-clear", n_clicks=0,
                        style=dict(btn, background="#fff", color="#64748b",
                                   border="1px solid #cbd5e1")),
        ]
    return html.Div(kids, style={"display": "flex", "alignItems": "center",
                                 "gap": "8px", "marginLeft": "auto",
                                 "flexWrap": "wrap"})


def active_filter_chip(text):
    """Small inline chip describing the applied filter (italic 'No filter' when
    none). Goes between Apply and Clear in apply_filter_controls."""
    if not text:
        return html.Span("No filter applied",
                         style={"fontSize": "10px", "color": "#94a3b8",
                                "fontStyle": "italic"})
    return html.Span(text, style={
        "display": "inline-block", "fontSize": "10px", "fontWeight": "700",
        "color": "#92400e", "background": "#fef3c7", "border": "1px solid #fbbf24",
        "borderRadius": "10px", "padding": "2px 10px", "whiteSpace": "nowrap"})


def sticky_bar(row_children, summary_id):
    """Wrap a control row + a dynamic one-line summary in the pinned bar."""
    return html.Div([
        html.Div(row_children, style={"display": "flex", "alignItems": "center",
                                      "gap": "14px", "flexWrap": "wrap"}),
        html.Div(id=summary_id, style={"fontSize": "11px", "color": "#475569",
                                       "marginTop": "8px", "fontWeight": "600",
                                       "borderTop": "1px dashed #e2e8f0",
                                       "paddingTop": "6px"}),
    ], style=STICKY_BAR)


SEV_NOTE = ("Severity thresholds: Critical >25%, High >10%, Medium >5%, "
            "Low >1% missing")


# ── Drift stat-test metadata (port of drift_page TEST_META) ───────────────

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


TEST_META = [
    {"key": "psi", "label": "PSI", "short": "PSI",
     "fmt": lambda v: "—" if v is None else fmt(v, 3),
     "level": _lvl_psi, "buckets": ["≤0.10", "0.10–0.20", ">0.20"],
     "help": ("Population Stability Index — compares the binned distribution of "
              "a variable now vs the reference period. Rule of thumb: ≤0.10 "
              "stable · 0.10–0.20 moderate shift · >0.20 significant shift.")},
    {"key": "ks_p", "label": "KS p-value", "short": "KS",
     "fmt": lambda v: "—" if v is None else fmt(v, 4),
     "level": _lvl_p, "buckets": ["p ≥ 0.05", "p 0.01–0.05", "p < 0.01"],
     "help": ("Kolmogorov–Smirnov p-value — probability the two periods' "
              "distributions are the same. Low p means a real shift: p<0.01 "
              "strong evidence of drift · p≥0.05 no significant change.")},
    {"key": "anova_p", "label": "ANOVA p-value", "short": "ANOVA",
     "fmt": lambda v: "—" if v is None else fmt(v, 4),
     "level": _lvl_p, "buckets": ["p ≥ 0.05", "p 0.01–0.05", "p < 0.01"],
     "help": ("Analysis-of-variance p-value on the group means — tests whether "
              "the variable's mean differs between the two periods. p<0.01 "
              "flags a significant mean shift · p≥0.05 no significant "
              "difference.")},
    {"key": "cohens_d", "label": "Cohen's d", "short": "Cohen",
     "fmt": lambda v: "—" if v is None else ("+" if v >= 0 else "") + fmt(v, 3),
     "level": _lvl_cohen, "buckets": ["|d| ≤ 0.2", "0.2–0.5", "> 0.5"],
     "help": ("Cohen's d — standardized difference between the two periods' "
              "means (in standard deviations). |d|≤0.2 negligible · 0.2–0.5 "
              "small/moderate · >0.5 large. Sign shows the direction.")},
    {"key": "js_div", "label": "JS Divergence", "short": "JS",
     "fmt": lambda v: "—" if v is None else fmt(v, 3),
     "level": _lvl_js, "buckets": ["≤ 0.2", "0.2–0.5", "> 0.5"],
     "help": ("Jensen–Shannon divergence — a 0–1 distance between the two "
              "distributions (0 = identical). ≤0.2 minor · 0.2–0.5 moderate · "
              ">0.5 large divergence.")},
]
TEST_BY_KEY = {t["key"]: t for t in TEST_META}

LEVEL_COLORS = {
    "red":   {"bg": "#fee2e2", "fg": "#991b1b"},
    "amber": {"bg": "#fef3c7", "fg": "#92400e"},
    "green": {"bg": "#dcfce7", "fg": "#166534"},
    "none":  {"bg": "#f1f5f9", "fg": "#64748b"},
}


def verdict_for(row) -> dict:
    """3+ red tests → Drift · 1–2 red → Mixed · else Stable."""
    red = sum(1 for t in TEST_META if t["level"](row.get(t["key"])) == "red")
    level = "red" if red >= 3 else "amber" if red >= 1 else "green"
    label = "⚠ Drift" if red >= 3 else "◐ Mixed" if red >= 1 else "✓ Stable"
    return {"level": level, "label": label, "red_count": red}


# ── Misc shared logic ─────────────────────────────────────────────────────

# Canonical missing-data severity — 4 buckets at 0 / ≤1% / ≤10% / >10%.
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


def missing_bucket(missing_pct) -> str:
    v = 0.0 if missing_pct is None else float(missing_pct)
    if v <= 0:
        return "No Missings"
    if v <= 1:
        return "Low"
    if v <= 10:
        return "Medium"
    return "High"


def dtype_bucket(row) -> str:
    t = str(row.get("schema_dtype") or "").lower()
    if any(s in t for s in ("float", "int", "decimal", "number")):
        return "Numeric"
    if "date" in t or "time" in t:
        return "Date"
    if any(s in t for s in ("text", "varchar", "char", "string")):
        return "Text"
    return "Other"


def get_q(metrics, q) -> dict:
    return (metrics.get("by_quarter") or {}).get(q) or {}
