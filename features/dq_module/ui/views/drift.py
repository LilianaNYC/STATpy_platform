"""Distribution Drift tab — port of pages/drift_page.py.

Two-question design (gotcha #6: this tab IGNORES the shared comparison mode):
  Q1 · Within-Portfolio Drift   — DASH_DATA.drift_q1 (12 recent Q-vs-Q-1 pairs)
  Q2 · Cross-Portfolio Drift    — DASH_DATA.drift_q2 (+ PSI heatmap, all shared Qs)

Own state machine: DRIFT_QUESTION / DRIFT_WINDOW / DRIFT_STAT_TEST /
DRIFT_PSI_VAR / DRIFT_SELECTED_VAR — all Dash inputs or a dcc.Store here.
Only PSI exists beyond the recent window ('all'); the other 4 tests are
precomputed for the recent 12 quarters only.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from ..common import (
    GRAPH_CFG, LEVEL_COLORS, SECTION, SECTION_TITLE, TEST_BY_KEY, TEST_META,
    empty_note, fig, fmt, fmt_n, help_tip, kpi_card, kpi_grid, q_label,
    question_bar, question_chip, verdict_for,
)

TAB = "drift"

# ── Hover-help copy (plain-English explanations) ──────────────────────────
DRIFT_HELP = (
    "Distribution drift measures how much each variable's value distribution "
    "has moved between two snapshots. Five statistical tests (PSI, KS, ANOVA, "
    "Cohen's d, JS divergence) each compare the current quarter against a "
    "reference period — the prior quarter (Within-Portfolio) or Port 2024 at "
    "the same quarter (Cross-Portfolio). Larger drift can signal data-quality "
    "breaks or genuine portfolio shifts."
)
SUMMARY_HELP = (
    "For the latest quarter, each variable is graded green / amber / red on "
    "this test against its threshold. The bar shows how the variables split "
    "across those three grades, and the counts beneath give the exact split."
)
RANKED_HELP = (
    "One row per variable, ranked by the selected stat test for the latest "
    "quarter (worst first). Each test compares the latest quarter's "
    "distribution against its reference period: the prior quarter for "
    "Within-Portfolio Drift, or Port 2024 at the same quarter for "
    "Cross-Portfolio Drift. The Verdict counts how many of the 5 tests fail "
    "their threshold."
)


# ── Data accessors ────────────────────────────────────────────────────────

def _active(metrics, question):
    return metrics.get("drift_q1" if question == "q1" else "drift_q2") or {}


def _window_size(window):
    return {"4q": 4, "8q": 8, "12q": 12}.get(window)


def _visible_quarters(metrics, question, window):
    active = _active(metrics, question)
    recent = active.get("recent_quarters") or []
    all_q = (active.get("all_quarters") if question == "q1"
             else active.get("shared_quarters")) or []
    n = _window_size(window)
    if n is None:
        return all_q
    return recent[-n:]


def _all_var_names(metrics):
    names = set()
    for key in ("drift_q1", "drift_q2"):
        by_q = (metrics.get(key) or {}).get("by_quarter") or {}
        for row in by_q.values():
            for v in row.get("by_variable") or []:
                names.add(v.get("column"))
    names.update(((metrics.get("time_series") or {}).get("psi_heatmap") or {}).keys())
    return sorted(n for n in names if n)


def _value_at(metrics, question, test_key, q, var):
    active = _active(metrics, question)
    row = (active.get("by_quarter") or {}).get(q)
    if row:
        for v in row.get("by_variable") or []:
            if v.get("column") == var:
                return v.get(test_key)
    if test_key == "psi":
        if question == "q2":
            return ((active.get("psi_heatmap") or {}).get(var) or {}).get(q)
        return (((metrics.get("time_series") or {}).get("psi_heatmap") or {})
                .get(var) or {}).get(q)
    return None


def _latest_q(metrics, question):
    recent = _active(metrics, question).get("recent_quarters") or []
    return recent[-1] if recent else None


def _question_chip(metrics, question, window):
    visible = _visible_quarters(metrics, question, window)
    rng = (f"{q_label(visible[0])} → {q_label(visible[-1])}" if visible else "—")
    bg = "#2563eb" if question == "q1" else "#7c3aed"
    label = "Within-Portfolio Drift" if question == "q1" else "Cross-Portfolio Drift"
    return question_chip(label, rng, bg)


def _var_button(name, selected, extra_style=None):
    style = {"fontFamily": "monospace", "fontSize": "10px", "padding": "5px 8px",
             "background": "#fff7ed" if selected else "#fff",
             "color": "#0f172a", "fontWeight": "700" if selected else "500",
             "border": "1px solid #f1f5f9", "cursor": "pointer",
             "whiteSpace": "nowrap", "width": "100%", "textAlign": "left"}
    if selected:
        style["borderLeft"] = "3px solid #9a3412"
    if extra_style:
        style.update(extra_style)
    return html.Button(name, id={"type": "dqd-drift-var", "index": name},
                       n_clicks=0, style=style)


# ── Layout ────────────────────────────────────────────────────────────────

def layout(metrics: dict):
    var_opts = ([{"label": "Average (all variables)", "value": "avg"}] +
                [{"label": v, "value": v} for v in _all_var_names(metrics)])

    selector = question_bar(
        TAB,
        [{"value": "q1", "label": "Within-Portfolio Drift"},
         {"value": "q2", "label": "Cross-Portfolio Drift"}],
        default="q1")

    window_picker = html.Div([
        html.Span("WINDOW", style={"fontSize": "10px", "fontWeight": "700",
                                   "color": "#64748b", "letterSpacing": ".05em"}),
        dcc.RadioItems(
            id=f"dqd-{TAB}-window",
            options=[{"label": "Last 4Q", "value": "4q"},
                     {"label": "Last 8Q", "value": "8q"},
                     {"label": "Last 12Q", "value": "12q"},
                     {"label": "All history", "value": "all"}],
            value="8q", inline=True,
            labelStyle={"marginRight": "14px", "fontSize": "12px"}),
        html.Span(id=f"dqd-{TAB}-window-note",
                  style={"fontSize": "11px", "color": "#475569",
                         "fontFamily": "monospace"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "10px",
              "flexWrap": "wrap", "padding": "8px 12px", "background": "#f8fafc",
              "border": "1px solid #e2e8f0", "borderRadius": "8px",
              "marginBottom": "14px"})

    test_dd = html.Div([
        html.Span("STAT TEST", style={"fontSize": "10px", "color": "#64748b",
                                      "fontWeight": "700",
                                      "letterSpacing": ".05em"}),
        dcc.Dropdown(id=f"dqd-{TAB}-stat-test", clearable=False, value="psi",
                     options=[{"label": t["label"], "value": t["key"]}
                              for t in TEST_META],
                     style={"width": "170px", "fontSize": "11px"}),
        html.Span("VARIABLE", style={"fontSize": "10px", "color": "#64748b",
                                     "fontWeight": "700", "letterSpacing": ".05em",
                                     "marginLeft": "14px"}),
        dcc.Dropdown(id=f"dqd-{TAB}-psi-var", clearable=False, value="avg",
                     options=var_opts, style={"width": "230px", "fontSize": "11px"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "8px",
              "flexWrap": "wrap"})

    return [
        html.Div([
            html.Div([
                html.H2(id=f"dqd-{TAB}-title", style={"margin": 0,
                                                      "fontSize": "20px"}),
                help_tip(DRIFT_HELP),
            ], style={"display": "flex", "alignItems": "center", "gap": "6px",
                      "marginBottom": "6px"}),
            html.P(id=f"dqd-{TAB}-desc",
                   style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
        ], style=SECTION),

        dcc.Store(id=f"dqd-{TAB}-selected", data=None),
        selector,
        window_picker,
        html.Div(id=f"dqd-{TAB}-kpis"),

        html.Div([
            html.Div(["Drift Summary — distribution by stat test ",
                      help_tip(SUMMARY_HELP),
                      html.Span(id=f"dqd-{TAB}-chip1")], style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-summary-note",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-summary-grid",
                     style={"display": "grid", "gridTemplateColumns": "repeat(5, 1fr)",
                            "gap": "10px"}),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div(["Drift Metric Over Time ",
                          html.Span(id=f"dqd-{TAB}-chip2")],
                         style=dict(SECTION_TITLE, margin=0)),
                test_dd,
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "8px",
                      "marginBottom": "6px"}),
            dcc.Graph(id=f"dqd-{TAB}-chart-trend", config=GRAPH_CFG),
            html.Div(id=f"dqd-{TAB}-trend-footer",
                     style={"marginTop": "8px", "fontSize": "10px",
                            "color": "#64748b"}),
        ], style=SECTION),

        html.Div([
            html.Div(["Drift Heatmap — variable × quarter ",
                      html.Span(id=f"dqd-{TAB}-chip3")], style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-heatmap-note",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-heatmap",
                     style={"overflowX": "auto", "maxHeight": "560px",
                            "overflowY": "auto", "border": "1px solid #e2e8f0",
                            "borderRadius": "6px"}),
            html.Div(id=f"dqd-{TAB}-heatmap-legend",
                     style={"marginTop": "8px", "fontSize": "10px",
                            "color": "#64748b", "display": "flex", "gap": "12px",
                            "flexWrap": "wrap"}),
        ], style=SECTION),

        html.Div([
            html.Div(["Ranked Variables — Statistical Tests for the Latest Snapshot",
                      help_tip(RANKED_HELP)],
                     style=dict(SECTION_TITLE, display="flex", alignItems="center")),
            html.Div("One variable per row, sorted by the selected stat test (worst "
                     "first). The Verdict column counts how many of the 5 tests fail. "
                     "Click a variable for its detail below.",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-ranked", style={"overflowX": "auto"}),
        ], style=SECTION),

        html.Div([
            html.Div(id=f"dqd-{TAB}-detail-title", style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-detail"),
        ], style=SECTION, id=f"dqd-{TAB}-detail-card"),
    ]


# ── Callbacks ─────────────────────────────────────────────────────────────

def register_callbacks(app, metrics: dict):

    @app.callback(
        Output(f"dqd-{TAB}-selected", "data"),
        Input({"type": "dqd-drift-var", "index": ALL}, "n_clicks"),
        Input(f"dqd-{TAB}-question", "value"),
        State(f"dqd-{TAB}-selected", "data"),
        prevent_initial_call=True,
    )
    def _select_var(clicks, question, selected):
        trig = ctx.triggered_id
        if trig == f"dqd-{TAB}-question":
            return None  # question switch resets the drilldown (setDriftQuestion)
        if not ctx.triggered or not ctx.triggered[0].get("value"):
            raise PreventUpdate
        name = trig["index"] if isinstance(trig, dict) else None
        if not name:
            raise PreventUpdate
        return None if selected == name else name

    @app.callback(
        Output(f"dqd-{TAB}-title", "children"),
        Output(f"dqd-{TAB}-desc", "children"),
        Output(f"dqd-{TAB}-question-desc", "children"),
        Output(f"dqd-{TAB}-question-detail", "children"),
        Output(f"dqd-{TAB}-window-note", "children"),
        Output(f"dqd-{TAB}-kpis", "children"),
        Output(f"dqd-{TAB}-summary-note", "children"),
        Output(f"dqd-{TAB}-summary-grid", "children"),
        Output(f"dqd-{TAB}-chart-trend", "figure"),
        Output(f"dqd-{TAB}-trend-footer", "children"),
        Output(f"dqd-{TAB}-heatmap-note", "children"),
        Output(f"dqd-{TAB}-heatmap", "children"),
        Output(f"dqd-{TAB}-heatmap-legend", "children"),
        Output(f"dqd-{TAB}-ranked", "children"),
        Output(f"dqd-{TAB}-detail-title", "children"),
        Output(f"dqd-{TAB}-detail", "children"),
        Output(f"dqd-{TAB}-chip1", "children"),
        Output(f"dqd-{TAB}-chip2", "children"),
        Output(f"dqd-{TAB}-chip3", "children"),
        Input(f"dqd-{TAB}-question", "value"),
        Input(f"dqd-{TAB}-window", "value"),
        Input(f"dqd-{TAB}-stat-test", "value"),
        Input(f"dqd-{TAB}-psi-var", "value"),
        Input(f"dqd-{TAB}-selected", "data"),
    )
    def _update(question, window, test_key, psi_var, selected):
        question = question or "q1"
        window = window or "8q"
        test_key = test_key or "psi"
        psi_var = psi_var or "avg"
        test = TEST_BY_KEY[test_key]
        active = _active(metrics, question)
        visible = _visible_quarters(metrics, question, window)
        latest_q = _latest_q(metrics, question)
        latest_row = (active.get("by_quarter") or {}).get(latest_q) or {}
        latest_vars = latest_row.get("by_variable") or []
        latest_by_var = {r.get("column"): r for r in latest_vars}
        recent_n = len(active.get("recent_quarters") or [])

        title = f"Distribution Drift · {active.get('label') or ''}"
        desc = active.get("description") or ""
        q_desc = ("Comparing Port 2025 against its own recent history"
                  if question == "q1" else
                  "Comparing Port 2025 vs Port 2024 (deltas at shared quarters)")
        q_detail = ("Is there a significant change in the behavior of the new portfolio "
                    "relative to its own previous periods? Each quarter is compared "
                    "against the previous quarter, same portfolio."
                    if question == "q1" else
                    "Is there a significant difference between the new portfolio and the "
                    "old one at the same shared quarters? Each shared quarter compared "
                    "across portfolios, with focus on the deltas.")
        window_note = (f"{len(visible)} Q · "
                       f"{q_label(visible[0]) if visible else '—'} → "
                       f"{q_label(visible[-1]) if visible else '—'}"
                       + (f"  (only PSI is available beyond the last {recent_n}Q)"
                          if window == "all" else ""))

        # ── KPIs ──
        n_vars = len(latest_vars)
        b_red = sum(1 for r in latest_vars if test["level"](r.get(test_key)) == "red")
        psis = [r.get("psi") or 0 for r in latest_vars]
        avg_psi = sum(psis) / n_vars if n_vars else 0
        max_psi = max(psis) if psis else 0
        verdicts = [verdict_for(r) for r in latest_vars]
        drift_n = sum(1 for v in verdicts if v["level"] == "red")
        mixed_n = sum(1 for v in verdicts if v["level"] == "amber")
        kpis = kpi_grid([
            kpi_card("Variables Analyzed", fmt_n(n_vars), "latest snapshot", icon="📊"),
            kpi_card(f"Red in {test['short']}", fmt_n(b_red), "test threshold",
                     icon="⚠️"),
            kpi_card("Verdict: Drift (3+ red)", fmt_n(drift_n), "across all 5 tests",
                     icon="🔴"),
            kpi_card("Verdict: Mixed (1-2 red)", fmt_n(mixed_n), "", icon="◐"),
            kpi_card("Avg PSI", fmt(avg_psi, 3), "", icon="📈"),
            kpi_card("Max PSI", fmt(max_psi, 3), "", icon="📉"),
        ], 6)

        summary_note = (f"For each of the 5 tests, how many variables fall in each band "
                        f"(green / amber / red) in the latest snapshot "
                        f"({q_label(latest_q) if latest_q else '—'}).")

        # ── Summary grid ──
        cards = []
        for t in TEST_META:
            g = a_ = r_ = 0
            for row in latest_vars:
                lvl = t["level"](row.get(t["key"]))
                if lvl == "green":
                    g += 1
                elif lvl == "amber":
                    a_ += 1
                elif lvl == "red":
                    r_ += 1
            total = g + a_ + r_ or 1
            is_active = t["key"] == test_key
            bar = html.Div([
                html.Div(style={"background": "#16a34a", "width": f"{g/total*100:.1f}%"}),
                html.Div(style={"background": "#d97706", "width": f"{a_/total*100:.1f}%"}),
                html.Div(style={"background": "#dc2626", "width": f"{r_/total*100:.1f}%"}),
            ], style={"display": "flex", "height": "10px", "borderRadius": "5px",
                      "overflow": "hidden", "background": "#f1f5f9",
                      "marginBottom": "8px"})
            cards.append(html.Div([
                html.Div([
                    html.Div([t["label"], help_tip(t["help"])],
                             style={"fontSize": "12px", "fontWeight": "700",
                                    "color": "#0f172a", "display": "flex",
                                    "alignItems": "center"}),
                    html.Div(f"{g + a_ + r_} vars", style={"fontSize": "10px",
                                                           "color": "#94a3b8"}),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "baseline", "marginBottom": "8px"}),
                bar,
                html.Div([
                    html.Span([html.Strong(str(g)), f" · {t['buckets'][0]}"],
                              style={"color": "#166534"}),
                    html.Span(html.Strong(str(a_)), style={"color": "#92400e"}),
                    html.Span([html.Strong(str(r_)), f" · {t['buckets'][2]}"],
                              style={"color": "#991b1b"}),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "fontSize": "10px"}),
            ], style={"background": "#fff",
                      "border": f"1px solid {'#0f172a' if is_active else '#e2e8f0'}",
                      "borderRadius": "8px", "padding": "12px"}))

        # ── Trend chart ──
        all_vars = _all_var_names(metrics)
        x_labels = [q_label(q) for q in visible]
        traces = []
        if psi_var == "avg":
            y_vals = []
            for q in visible:
                vals = [v for v in (_value_at(metrics, question, test_key, q, c)
                                    for c in all_vars) if v is not None]
                y_vals.append(sum(vals) / len(vals) if vals else None)
            traces.append(go.Scatter(
                x=x_labels, y=y_vals, name=f"Average {test['short']}",
                mode="lines+markers",
                line={"color": "#2563eb" if question == "q1" else "#7c3aed",
                      "width": 2}, marker={"size": 4}, connectgaps=True))
        else:
            y_vals = [_value_at(metrics, question, test_key, q, psi_var)
                      for q in visible]
            traces.append(go.Scatter(
                x=x_labels, y=y_vals, name=f"{test['short']} · {psi_var}",
                mode="lines+markers", line={"color": "#dc2626", "width": 2},
                marker={"size": 4}, connectgaps=True))

        thresholds = {
            "psi": [(0.20, "#dc2626", "dot", "Significant (0.20)"),
                    (0.10, "#d97706", "dash", "Moderate (0.10)")],
            "ks_p": [(0.05, "#dc2626", "dot", "p = 0.05"),
                     (0.01, "#7c2d12", "dash", "p = 0.01")],
            "anova_p": [(0.05, "#dc2626", "dot", "p = 0.05"),
                        (0.01, "#7c2d12", "dash", "p = 0.01")],
            "cohens_d": [(0.50, "#dc2626", "dot", "|d| = 0.5"),
                         (0.20, "#d97706", "dash", "|d| = 0.2"),
                         (-0.20, "#d97706", "dash", "|d| = -0.2"),
                         (-0.50, "#dc2626", "dot", "|d| = -0.5")],
            "js_div": [(0.50, "#dc2626", "dot", "0.50"),
                       (0.20, "#d97706", "dash", "0.20")],
        }.get(test_key, [])
        for y, c, dash_style, label in thresholds:
            traces.append(go.Scatter(x=x_labels, y=[y] * len(x_labels), name=label,
                                     mode="lines",
                                     line={"color": c, "width": 1, "dash": dash_style},
                                     hoverinfo="skip"))

        all_y = [v for t_ in traces for v in (t_.y or []) if v is not None]
        y_max, y_min = (max(all_y) if all_y else 1), (min(all_y) if all_y else 0)
        y_range = ([min(-1, y_min * 1.1), max(1, y_max * 1.1)]
                   if test_key == "cohens_d" else [0, max(0.5, y_max * 1.1)])
        trend = go.Figure(traces)
        trend.update_layout(
            margin={"t": 10, "r": 10, "b": 50, "l": 60}, height=260,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"tickfont": {"size": 9}, "tickangle": -45},
            yaxis={"range": y_range, "gridcolor": "#f1f5f9", "tickfont": {"size": 9},
                   "title": test["label"]},
            showlegend=True, legend={"orientation": "h", "y": 1.18,
                                     "font": {"size": 9}})
        trend_footer = ("" if window != "all" or test_key == "psi" else
                        f"Note: {test['label']} is precomputed only for the last "
                        f"{recent_n} quarters. Older quarters are omitted from this "
                        "chart.")

        heatmap_note = html.Span([
            "Cell color reflects ", html.Strong(test["label"]),
            " for each quarter in the visible window. The ",
            html.Strong("Verdict"),
            " column summarizes all 5 tests for the latest snapshot. Click a "
            "variable name to see its detail below."])

        # ── Heatmap ──
        hm_latest = visible[-1] if visible else None
        reverse = test_key in ("ks_p", "anova_p")

        def rank_key(v):
            val = _value_at(metrics, question, test_key, hm_latest, v)
            if val is None:
                return float("inf")
            return val if reverse else -val

        vars_ordered = sorted(all_vars, key=rank_key)[:30]

        th = {"padding": "5px 8px", "background": "#1e293b", "color": "#fff",
              "fontSize": "9px", "fontWeight": "600", "border": "1px solid #1e293b",
              "whiteSpace": "nowrap", "textAlign": "center"}
        header = html.Tr(
            [html.Th("Variable", style=dict(th, background="#0f1d35",
                                            textAlign="left", fontSize="10px"))] +
            [html.Th(q_label(q), style=th) for q in visible] +
            [html.Th("Verdict", style=dict(th, background="#0f1d35",
                                           fontSize="10px"))])

        body = []
        for v in vars_ordered:
            cells = [html.Td(_var_button(v, selected == v), style={"padding": 0})]
            for q in visible:
                val = _value_at(metrics, question, test_key, q, v)
                if val is None:
                    cells.append(html.Td("—", style={
                        "textAlign": "center", "padding": "4px",
                        "background": "#fafafa", "color": "#cbd5e1",
                        "fontSize": "10px", "border": "1px solid #fff"}))
                else:
                    c = LEVEL_COLORS[test["level"](val)]
                    cells.append(html.Td(test["fmt"](val), style={
                        "textAlign": "center", "padding": "4px 6px",
                        "background": c["bg"], "color": c["fg"], "fontSize": "10px",
                        "fontWeight": "600", "border": "1px solid #fff"}))
            r = latest_by_var.get(v)
            verdict = verdict_for(r) if r else {"level": "none", "label": "—",
                                                "red_count": 0}
            vc = LEVEL_COLORS[verdict["level"]]
            cells.append(html.Td([verdict["label"], html.Br(),
                                  html.Span(f"{verdict['red_count']}/5 fail",
                                            style={"fontSize": "8px",
                                                   "fontWeight": "500",
                                                   "opacity": ".7"})],
                                 style={"textAlign": "center", "padding": "5px 8px",
                                        "background": vc["bg"], "color": vc["fg"],
                                        "fontSize": "10px", "fontWeight": "700",
                                        "border": "1px solid #fff"}))
            body.append(html.Tr(cells))

        heatmap = html.Table([html.Thead(header), html.Tbody(body)],
                             style={"borderCollapse": "collapse", "fontSize": "11px"})

        def swatch(color, text):
            return html.Span([html.Span(style={"display": "inline-block",
                                               "width": "12px", "height": "12px",
                                               "background": color,
                                               "borderRadius": "2px",
                                               "marginRight": "4px",
                                               "verticalAlign": "middle"}), text])

        legend = [
            swatch("#dcfce7", f"Stable · {test['buckets'][0]}"),
            swatch("#fef3c7", f"Mixed · {test['buckets'][1]}"),
            swatch("#fee2e2", f"Drift · {test['buckets'][2]}"),
            html.Span(f"Top {len(vars_ordered)} variables (ranked by {test['label']} "
                      "in the latest quarter). Click a variable for detail.",
                      style={"marginLeft": "auto", "fontStyle": "italic"}),
        ]

        # ── Ranked table ──
        if not latest_vars:
            ranked = empty_note("No data available for the latest snapshot.")
        else:
            def sort_key(r):
                v = r.get(test_key)
                if v is None:
                    return float("inf")
                if test_key == "cohens_d":
                    return -abs(v)
                return v if reverse else -v

            rows = []
            for r in sorted(latest_vars, key=sort_key):
                verdict = verdict_for(r)
                vc = LEVEL_COLORS[verdict["level"]]
                is_sel = selected == r.get("column")
                cells = [html.Td(_var_button(r.get("column"), is_sel,
                                             {"fontSize": "11px",
                                              "fontWeight": "700" if is_sel else "600",
                                              "padding": "6px 10px"}),
                                 style={"padding": 0})]
                for t in TEST_META:
                    v = r.get(t["key"])
                    c = LEVEL_COLORS[t["level"](v)]
                    style = {"textAlign": "center", "background": c["bg"],
                             "color": c["fg"], "fontWeight": "600", "padding": "6px",
                             "fontSize": "11px"}
                    if t["key"] == test_key:
                        style["outline"] = "2px solid #0f172a"
                        style["outlineOffset"] = "-2px"
                    cells.append(html.Td(t["fmt"](v), style=style))
                cells.append(html.Td([verdict["label"], html.Br(),
                                      html.Span(f"{verdict['red_count']}/5 fail",
                                                style={"fontSize": "9px",
                                                       "fontWeight": "500",
                                                       "opacity": ".7"})],
                                     style={"textAlign": "center",
                                            "background": vc["bg"], "color": vc["fg"],
                                            "fontWeight": "700", "padding": "6px",
                                            "fontSize": "11px"}))
                rows.append(html.Tr(cells,
                                    style={"background": "#fff7ed"} if is_sel else None))

            hdr = {"fontSize": "10px", "fontWeight": "700",
                   "textTransform": "uppercase", "color": "#64748b",
                   "background": "#f8fafc", "padding": "6px 8px"}
            ranked = html.Table([
                html.Thead(html.Tr(
                    [html.Th("Variable", style=dict(hdr, textAlign="left"))] +
                    [html.Th(t["short"], title=t["label"],
                             style=dict(hdr, textAlign="center")) for t in TEST_META] +
                    [html.Th("Verdict", style=dict(hdr, textAlign="center"))])),
                html.Tbody(rows),
            ], style={"width": "100%", "borderCollapse": "collapse",
                      "fontSize": "12px"})

        # ── Detail panel ──
        detail_title = ["Variable Detail"]
        if selected:
            detail_title += [" · ", html.Code(selected)]
        if not selected:
            detail = html.Div("Click any variable in the heatmap or the ranked table "
                              "to see its detail here.",
                              style={"padding": "20px", "textAlign": "center",
                                     "color": "#94a3b8", "fontSize": "12px",
                                     "fontStyle": "italic"})
        else:
            row = latest_by_var.get(selected)
            if not row:
                detail = html.Div(["No data for ", html.Code(selected), " at ",
                                   q_label(latest_q), "."],
                                  style={"padding": "16px", "color": "#94a3b8",
                                         "fontSize": "12px"})
            else:
                verdict = verdict_for(row)
                vc = LEVEL_COLORS[verdict["level"]]
                cmp_labels = ({"ref": "Prior Q", "cur": q_label(latest_q)}
                              if question == "q1" else
                              {"ref": f"Port 2024 · {q_label(latest_q)}",
                               "cur": f"Port 2025 · {q_label(latest_q)}"})

                def stat_line(label, cur, ref, suffix=""):
                    d_raw = (cur - ref) if cur is not None and ref is not None else None
                    if d_raw is None or abs(d_raw) < 1e-6:
                        d_el = html.Span("—", style={"color": "#64748b"})
                    else:
                        c = "#dc2626" if d_raw > 0 else "#16a34a"
                        sym = "▲" if d_raw > 0 else "▼"
                        d_el = html.Span(f"{sym} {'+' if d_raw >= 0 else ''}"
                                         f"{fmt(d_raw, 3)}{suffix}",
                                         style={"color": c, "fontWeight": "600"})
                    cell = {"textAlign": "right", "fontFamily": "monospace",
                            "padding": "5px 8px",
                            "borderBottom": "1px solid #f1f5f9"}
                    return html.Tr([
                        html.Td(label, style={"color": "#64748b", "padding": "5px 8px",
                                              "borderBottom": "1px solid #f1f5f9"}),
                        html.Td("—" if cur is None else fmt(cur, 3) + suffix,
                                style=cell),
                        html.Td("—" if ref is None else fmt(ref, 3) + suffix,
                                style=cell),
                        html.Td(d_el, style=dict(cell, fontFamily="inherit")),
                    ])

                hdr = {"fontSize": "10px", "fontWeight": "700", "color": "#64748b",
                       "background": "#f8fafc", "padding": "6px 8px",
                       "textAlign": "right"}
                stats = html.Table([
                    html.Thead(html.Tr([html.Th("", style=dict(hdr, textAlign="left")),
                                        html.Th(cmp_labels["cur"], style=hdr),
                                        html.Th(cmp_labels["ref"], style=hdr),
                                        html.Th("Δ", style=hdr)])),
                    html.Tbody([
                        stat_line("Mean", row.get("cur_mean"), row.get("ref_mean")),
                        stat_line("Median", row.get("cur_median"), row.get("ref_median")),
                        stat_line("Std Dev", row.get("cur_std"), row.get("ref_std")),
                        stat_line("Missing %", row.get("cur_missing_pct"),
                                  row.get("ref_missing_pct"), "%"),
                    ]),
                ], style={"fontSize": "11px", "width": "100%",
                          "borderCollapse": "collapse"})

                test_cells = []
                for t in TEST_META:
                    v = row.get(t["key"])
                    c = LEVEL_COLORS[t["level"](v)]
                    test_cells.append(html.Div([
                        html.Div(t["label"], style={"fontSize": "9px",
                                                    "fontWeight": "700",
                                                    "letterSpacing": ".05em",
                                                    "textTransform": "uppercase"}),
                        html.Div(t["fmt"](v), style={"fontSize": "16px",
                                                     "fontWeight": "800",
                                                     "marginTop": "2px"}),
                    ], style={"background": c["bg"], "color": c["fg"],
                              "padding": "8px 10px", "borderRadius": "6px",
                              "textAlign": "center"}))

                detail = html.Div([
                    html.Div([
                        html.Div(selected, style={"fontSize": "14px",
                                                  "fontWeight": "700",
                                                  "fontFamily": "monospace"}),
                        html.Span(f"{verdict['label']} · {verdict['red_count']}/5 fail",
                                  style={"fontSize": "10px", "fontWeight": "700",
                                         "color": "#fff", "background": vc["fg"],
                                         "padding": "2px 8px",
                                         "borderRadius": "10px"}),
                    ], style={"display": "flex", "alignItems": "baseline",
                              "gap": "10px", "marginBottom": "10px",
                              "flexWrap": "wrap"}),
                    html.Div([
                        html.Div([
                            html.Div(f"Distribution comparison at the "
                                     f"{q_label(latest_q)} snapshot.",
                                     style={"fontSize": "11px", "color": "#64748b",
                                            "marginBottom": "8px"}),
                            stats,
                        ]),
                        html.Div([
                            html.Div(f"Stat Tests at {q_label(latest_q)}",
                                     style={"fontSize": "11px", "fontWeight": "700",
                                            "color": "#0f172a",
                                            "textTransform": "uppercase",
                                            "letterSpacing": ".05em",
                                            "marginBottom": "8px"}),
                            html.Div(test_cells,
                                     style={"display": "grid",
                                            "gridTemplateColumns": "repeat(5, 1fr)",
                                            "gap": "6px"}),
                        ]),
                    ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                              "gap": "16px", "alignItems": "start"}),
                ])

        chip = _question_chip(metrics, question, window)
        return (title, desc, q_desc, q_detail, window_note, kpis, summary_note,
                cards, trend, trend_footer, heatmap_note, heatmap, legend, ranked,
                detail_title, detail,
                _question_chip(metrics, question, window),
                _question_chip(metrics, question, window), chip)
