"""Overview tab — the dashboard's front door (triage launchpad).

Answers "is the portfolio data healthy this quarter, and where do I go?" in one
screen. A Within/Cross-Portfolio toggle (Population-style) flips each domain
card's headline between the current snapshot + since-last-quarter delta (Within)
and the Port 2024 → Port 2025 scorecard line (Cross); cards without a
portfolio-level cross metric say so and point to their tab. Every domain card is
clickable and navigates to its tab. A priority worklist surfaces the governance
issues + recommendations (the "look here first"), and Cross mode reveals the
full Port-2024-vs-Port-2025 scorecard. Deep trends live in the Time Series tab.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from .common import (
    CARD, GRID2, MISSING_BUCKETS, MUTED, SECTION, SECTION_TITLE, SEV_NOTE, STATUS,
    arrow_delta, compare_selector, empty_note, fmt, fmt_n, get_q, help_tip,
    missing_bucket, pct, q_label, simple_table, spark, sticky_bar, td,
)

TAB = "overview"

# Overview-card → destination. Standalone app: these switch the internal
# dcc.Tabs (dqd-main-tabs). Under STATpy (as_pages=True) each tab is its own
# page, so cards become dcc.Link()s to these paths instead.
PATHS = {
    "overview": "/dq-overview", "schema": "/dq-schema",
    "completeness": "/dq-completeness", "rules": "/dq-rules",
    "population": "/dq-population", "summary_details": "/dq-balance",
    "drift": "/dq-drift", "timeseries": "/dq-timeseries",
}

RAG_COLOR = {"RED": "#dc2626", "AMBER": "#d97706", "GREEN": "#16a34a",
             "GRAY": "#94a3b8", "": "#94a3b8"}
SEV_COLOR = {"Critical": "#dc2626", "High": "#d97706", "Medium": "#ca8a04",
             "Low": "#16a34a"}
SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

WORKLIST_HELP = (
    "Open data-quality issues (from the governance rule checks) and the "
    "recommended remediation actions, ordered by severity. Start at the top — "
    "this is the dashboard's 'look here first'."
)
SCORECARD_HELP = (
    "Portfolio-level Port 2024 vs Port 2025 benchmark. Each metric is graded "
    "RED / AMBER / GREEN against its tolerance; 'Flag' says why. This is the "
    "cross-portfolio counterpart to the within-portfolio cards above."
)


# ── Small render helpers ──────────────────────────────────────────────────

def _dot(color, size=10):
    return html.Span(style={"width": f"{size}px", "height": f"{size}px",
                            "borderRadius": "50%", "background": color,
                            "display": "inline-block", "flex": "0 0 auto",
                            "verticalAlign": "middle"})


def _pill(text, color):
    return html.Span(text, style={"fontSize": "9px", "fontWeight": "700",
                                  "color": "#fff", "background": color,
                                  "padding": "1px 7px", "borderRadius": "9px",
                                  "letterSpacing": ".03em", "flex": "0 0 auto"})


def _sc_row(metrics, *needles):
    """First scorecard row whose metric contains all needles (case-insensitive)."""
    for r in (metrics.get("scorecard") or {}).get("rows") or []:
        m = (r.get("metric") or "").lower()
        if all(n.lower() in m for n in needles):
            return r
    return None


def _sev_counts(comp):
    cnt = {b: 0 for b in MISSING_BUCKETS}
    for c in comp.get("by_column") or []:
        cnt[missing_bucket(c.get("missing_pct"))] += 1
    return cnt


# ── Domain specs (one per analysis tab) ───────────────────────────────────

def _domain_specs(metrics):
    d = get_q(metrics, metrics["latest_quarter"])
    comp = d.get("completeness") or {}
    rules = d.get("business_rules") or {}
    pop = d.get("population") or {}
    drift = d.get("drift") or {}
    schema = d.get("schema") or {}
    gov = d.get("governance") or {}
    qoq = d.get("qoq") or {}
    sev = _sev_counts(comp)
    overall = comp.get("overall_pct") if comp.get("overall_pct") is not None else 100
    rating_status = {"GREEN": "green", "MODERATE": "amber", "RED": "red"}.get(
        gov.get("dq_rating"), "gray")
    psi_label = pop.get("psi_label")
    ds = drift.get("drift_status")
    anoms = metrics.get("summary_count_anomalies") or []

    return [
        {"tab": "completeness", "title": "Completeness",
         "status": "red" if overall < 95 else ("amber" if overall < 98 else "green"),
         "primary": f"Overall {pct(overall)} · High {sev['High']} · "
                    f"Medium {sev['Medium']} · Low {sev['Low']}",
         "qoq": qoq.get("completeness_delta"), "qoq_good_up": True,
         "qoq_sub": "pp overall", "cross": _sc_row(metrics, "completeness")},
        {"tab": "rules", "title": "Business Rules & Gov.",
         "status": rating_status,
         "primary": f"Rating {gov.get('dq_rating') or '—'} · "
                    f"{rules.get('rules_failed') or 0} failed "
                    f"({rules.get('critical_failures') or 0} crit.)",
         "qoq": qoq.get("failure_rate_delta"), "qoq_good_up": False,
         "qoq_sub": "pp failure rate", "qoq_digits": 2, "cross": None},
        {"tab": "population", "title": "Population Stability",
         "status": ("red" if psi_label == "Significant"
                    else ("amber" if psi_label == "Moderate" else "green")),
         "primary": f"Total {fmt_n(pop.get('total'))} · New {pop.get('new') or 0} · "
                    f"PSI {fmt(pop.get('psi'), 2)} ({psi_label or '—'})",
         "qoq": qoq.get("total_records_delta"), "qoq_good_up": True,
         "qoq_sub": "records", "qoq_digits": 0,
         "cross": _sc_row(metrics, "total record count")},
        {"tab": "drift", "title": "Distribution Drift",
         "status": ("red" if ds == "Critical"
                    else ("amber" if ds == "Elevated" else "green")),
         "primary": f"Avg PSI {fmt(drift.get('avg_psi'), 3)} · "
                    f"{drift.get('sig_drift_count') or 0} sig · {ds or '—'}",
         "qoq": qoq.get("avg_psi_delta"), "qoq_good_up": False,
         "qoq_sub": "avg PSI", "qoq_digits": 4, "cross": None},
        {"tab": "schema", "title": "Schema Quality",
         "status": ("red" if (schema.get("breaking_changes") or 0) > 0
                    else ("amber" if (schema.get("modified_columns") or 0) > 0
                          else "green")),
         "primary": f"{schema.get('total_columns') or 0} cols · "
                    f"Quality {pct(schema.get('quality_score'))} · "
                    f"{schema.get('tables_with_changes') or 0} changes",
         "qoq": qoq.get("schema_quality_delta"), "qoq_good_up": True,
         "qoq_sub": "pp quality", "cross": None},
        {"tab": "summary_details", "title": "Balance & Composition",
         "status": "amber" if anoms else "green",
         "primary": (f"{len(anoms)} segment(s) flagged for reconciliation"
                     if anoms else "No reconciliation anomalies"),
         "qoq": None, "within_note": "vs prior year-end · open the tab to reconcile",
         "cross": _sc_row(metrics, "total balance")},
    ]


def _card(spec, cross, as_pages=False):
    pal = STATUS[spec["status"]]

    if cross:
        row = spec.get("cross")
        if row:
            rag = (row.get("rag") or "").upper()
            mode_line = html.Div([
                html.Span("Port 2024 → 2025: ", style={"color": "#64748b"}),
                html.Strong(f"{row.get('v24')} → {row.get('v25')}",
                            style={"color": "#0f172a"}),
                html.Span(f"  Δ {row.get('delta')}  ",
                          style={"color": RAG_COLOR.get(rag, "#64748b"),
                                 "fontWeight": "700"}),
                _pill(rag or "—", RAG_COLOR.get(rag, "#94a3b8")),
            ], style={"fontSize": "11px", "marginTop": "5px",
                      "display": "flex", "alignItems": "center", "gap": "2px",
                      "flexWrap": "wrap"})
        else:
            mode_line = html.Div("No portfolio-level cross metric — open the tab "
                                 "for its Cross-Portfolio view.",
                                 style={"fontSize": "10px", "color": "#94a3b8",
                                        "fontStyle": "italic", "marginTop": "5px"})
    elif spec.get("qoq") is not None:
        mode_line = html.Div([
            html.Span("Since last Q: ", style={"color": "#64748b"}),
            arrow_delta(spec["qoq"], good_when_up=spec.get("qoq_good_up", True),
                        d_digits=spec.get("qoq_digits", 2)),
            html.Span(f" {spec.get('qoq_sub', '')}",
                      style={"color": "#94a3b8", "fontSize": "10px"}),
        ], style={"fontSize": "11px", "marginTop": "5px"})
    else:
        mode_line = html.Div(spec.get("within_note", ""),
                             style={"fontSize": "10px", "color": "#94a3b8",
                                    "fontStyle": "italic", "marginTop": "5px"})

    inner = [
        html.Div([
            html.Span(spec["title"], style={"fontSize": "13px", "fontWeight": "700",
                                            "color": "#0f172a"}),
            html.Span("›", style={"marginLeft": "auto", "color": "#cbd5e1",
                                  "fontSize": "18px", "fontWeight": "700"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}),
        html.Div([
            _dot(pal["dot"]),
            html.Span(spec["status"].upper(),
                      style={"fontSize": "10px", "fontWeight": "700",
                             "color": pal["dot"], "background": pal["bg"],
                             "padding": "2px 8px", "borderRadius": "10px"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "6px",
                  "marginBottom": "6px"}),
        html.Div(spec["primary"], style={"fontSize": "12px", "color": "#334155"}),
        mode_line,
    ]
    if as_pages:
        # STATpy: each tab is its own page — navigate by link, no callback.
        return dcc.Link(html.Div(inner, style=dict(CARD, cursor="pointer")),
                        href=PATHS.get(spec["tab"], "/"),
                        style={"textDecoration": "none", "color": "inherit"})
    return html.Div(inner, id={"type": "dqd-ov-card", "index": spec["tab"]},
                    n_clicks=0, title="Open the " + spec["title"] + " tab",
                    style=dict(CARD, cursor="pointer"))


# ── Priority worklist (governance issues + recommendations) ───────────────

def _worklist(metrics):
    gov = get_q(metrics, metrics["latest_quarter"]).get("governance") or {}
    recs = gov.get("recommendations") or []
    issues = sorted(gov.get("issues") or [],
                    key=lambda i: (SEV_ORDER.get(i.get("severity"), 9),
                                   -(i.get("affected_pct") or 0)))

    rec_els = []
    for r in recs:
        pr = r.get("priority") or "—"
        rec_els.append(html.Div([
            html.Div([_pill(pr, SEV_COLOR.get(pr, "#64748b")),
                      html.Span(r.get("text") or "", style={"fontSize": "12px",
                                                            "color": "#0f172a",
                                                            "fontWeight": "600"})],
                     style={"display": "flex", "gap": "8px", "alignItems": "baseline"}),
            html.Div(f"{r.get('owner') or '—'} · ETA {r.get('eta') or '—'}",
                     style={"fontSize": "10px", "color": "#94a3b8",
                            "marginLeft": "2px"}),
        ], style={"padding": "7px 0", "borderBottom": "1px solid #f1f5f9"}))
    if not rec_els:
        rec_els = [empty_note("No open recommendations.")]

    issue_els = []
    for i in issues[:6]:
        sv = i.get("severity") or "—"
        issue_els.append(html.Div([
            html.Div([_pill(sv, SEV_COLOR.get(sv, "#64748b")),
                      html.Span(i.get("name") or "", style={"fontSize": "12px",
                                                           "fontWeight": "600",
                                                           "color": "#0f172a"}),
                      html.Span(f"{fmt(i.get('affected_pct'), 1)}% of records",
                                style={"marginLeft": "auto", "fontSize": "10px",
                                       "color": "#64748b", "fontFamily": "monospace",
                                       "whiteSpace": "nowrap"})],
                     style={"display": "flex", "gap": "8px", "alignItems": "baseline"}),
            html.Div(i.get("root_cause") or "", style={"fontSize": "10px",
                                                       "color": "#94a3b8",
                                                       "marginTop": "1px"}),
        ], style={"padding": "7px 0", "borderBottom": "1px solid #f1f5f9"}))
    if not issue_els:
        issue_els = [empty_note("No open issues.")]

    def col(title, kids):
        return html.Div([
            html.Div(title, style={"fontSize": "10px", "fontWeight": "700",
                                   "color": "#64748b", "textTransform": "uppercase",
                                   "letterSpacing": ".05em", "marginBottom": "4px"}),
            *kids,
        ], style=dict(CARD, padding="12px 14px"))

    return html.Div([
        html.Div(["Priority Worklist — what to look at first", help_tip(WORKLIST_HELP)],
                 style=dict(SECTION_TITLE, display="flex", alignItems="center")),
        html.Div([col("Recommended actions", rec_els),
                  col(f"Open issues ({len(issues)})", issue_els)], style=GRID2),
    ], style=SECTION)


# ── Cross-Portfolio scorecard (shown in Cross mode) ───────────────────────

def _scorecard_section(metrics):
    sc = metrics.get("scorecard") or {}
    rows = sc.get("rows") or []
    if not rows:
        return html.Div()
    body = []
    for r in rows:
        rag = (r.get("rag") or "").upper()
        body.append(html.Tr([
            td(r.get("metric"), fontWeight="600", color="#0f172a"),
            td(r.get("field") or "", color="#94a3b8", fontFamily="monospace",
               fontSize="10px"),
            td(str(r.get("v24")), textAlign="right", fontFamily="monospace"),
            td(str(r.get("v25")), textAlign="right", fontFamily="monospace"),
            td(str(r.get("delta")), textAlign="right", fontFamily="monospace",
               color=RAG_COLOR.get(rag, "#475569"), fontWeight="700"),
            td(_pill(rag or "—", RAG_COLOR.get(rag, "#94a3b8"))),
            td(r.get("red_flag") or "", color="#64748b", fontSize="10px"),
        ]))
    table = simple_table(
        ["Metric", "Field", f"Port 2024 ({sc.get('quarter_24') or 'P24'})",
         f"Port 2025 ({sc.get('quarter_25') or 'P25'})", "Δ", "RAG", "Flag"], body,
        header_styles=[None, None, {"textAlign": "right"}, {"textAlign": "right"},
                       {"textAlign": "right"}, None, None])
    return html.Div([
        html.Div(["Cross-Portfolio Scorecard — Port 2024 vs Port 2025",
                  help_tip(SCORECARD_HELP)],
                 style=dict(SECTION_TITLE, display="flex", alignItems="center")),
        html.Div(table, style={"overflowX": "auto"}),
    ], style=SECTION)


# ── Sparkline strip (12Q context; deep trends → Time Series) ──────────────

def _spark_row(label, values, latest_text):
    vals = [v for v in (values or []) if v is not None]
    rng = (f"{fmt(min(vals), 2)} → {fmt(max(vals), 2)}" if vals else "—")
    return html.Tr([
        html.Td(label, style={"fontSize": "11px", "fontWeight": "600",
                              "color": "#334155", "padding": "5px 10px 5px 0",
                              "whiteSpace": "nowrap"}),
        html.Td(latest_text, style={"fontSize": "12px", "fontWeight": "700",
                                    "color": "#0f172a", "padding": "5px 14px 5px 0",
                                    "textAlign": "right", "whiteSpace": "nowrap"}),
        html.Td(spark(values), style={"fontFamily": "monospace", "fontSize": "14px",
                                      "color": "#2563eb", "padding": "5px 14px 5px 0",
                                      "letterSpacing": "1px"}),
        html.Td(f"12Q range: {rng}", style={"fontSize": "10px", "color": "#94a3b8",
                                            "padding": "5px 0",
                                            "whiteSpace": "nowrap"}),
    ])


def _spark_strip(metrics):
    ts = metrics.get("time_series") or {}

    def tail(key, value_key):
        return [r.get(value_key) for r in (ts.get(key) or [])[-12:]]

    comp = tail("completeness_over_time", "value")
    psi = tail("psi_over_time", "avg_psi")
    fail = tail("failure_rate_over_time", "failure_rate_pct")
    pop = tail("population_over_time", "total")

    rows = [
        _spark_row("Completeness %", comp, pct(comp[-1] if comp else None)),
        _spark_row("Avg PSI (drift)", psi, fmt(psi[-1] if psi else None, 3)),
        _spark_row("Rule failure rate %", fail, pct(fail[-1] if fail else None)),
        _spark_row("Population (records)", pop, fmt_n(pop[-1] if pop else None)),
    ]
    return html.Div([
        html.Div("Last 12 quarters at a glance (Port 2025)", style=SECTION_TITLE),
        html.Table(html.Tbody(rows), style={"borderCollapse": "collapse"}),
        html.Div("Trends shown for context only — full trend analytics "
                 "(overlays, anomalies, correlations, forecast) live in the "
                 "Time Series tab.", style=dict(MUTED, marginTop="8px")),
    ], style=SECTION)


# ── Layout ────────────────────────────────────────────────────────────────

def _data_status(metrics):
    """One-line 'what data am I looking at' indicator for the refresh bar."""
    return (f"Data as of {metrics.get('data_as_of', '—')}  ·  "
            f"run {metrics.get('run_id', '—')}  ·  "
            f"latest quarter {q_label(metrics.get('latest_quarter'))}  ·  "
            f"source {metrics.get('source', '—')}")


def _data_bar(metrics):
    """Top strip: what data is loaded + an Update button that rebuilds it."""
    return html.Div([
        dcc.Store(id=f"dqd-{TAB}-data-version", data=0),
        html.Div([
            html.Span("DATA", style={"fontSize": "9px", "fontWeight": "700",
                                     "color": "#64748b", "letterSpacing": ".06em"}),
            dcc.Loading(
                html.Span(_data_status(metrics), id=f"dqd-{TAB}-data-status",
                          style={"fontSize": "11px", "color": "#475569",
                                 "fontFamily": "monospace"}),
                type="dot", color="#0f1d35"),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                  "flexWrap": "wrap"}),
        html.Button("Update data", id=f"dqd-{TAB}-refresh", n_clicks=0,
                    title="Rebuild metrics from the configured source "
                          "(config.yaml data.source) — ~1–2 min.",
                    style={"marginLeft": "auto", "fontSize": "11px",
                           "fontWeight": "700", "padding": "5px 14px",
                           "borderRadius": "6px", "cursor": "pointer",
                           "background": "#0f1d35", "color": "#fff",
                           "border": "1px solid #0f1d35"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "12px",
              "flexWrap": "wrap", "padding": "8px 12px", "marginBottom": "12px",
              "background": "#f8fafc", "border": "1px solid #e2e8f0",
              "borderRadius": "8px"})


def _header(metrics):
    """Title + DQ rating badge + one-line 'why' — rebuilt live on data refresh."""
    cq = metrics["latest_quarter"]
    gov = get_q(metrics, cq).get("governance") or {}
    rating = gov.get("dq_rating") or "—"
    pal = STATUS[{"GREEN": "green", "MODERATE": "amber", "RED": "red"}.get(rating, "gray")]
    non_green = [s["title"] for s in _domain_specs(metrics) if s["status"] != "green"]
    why = ("All domains are green this snapshot." if not non_green
           else "Needs attention: " + ", ".join(non_green) + ".")
    return [
        html.Div([
            html.H2(f"Portfolio DQ Overview — {q_label(cq)}",
                    style={"margin": 0, "fontSize": "20px"}),
            html.Span(rating, style={"fontSize": "11px", "fontWeight": "700",
                                     "color": pal["dot"], "background": pal["bg"],
                                     "padding": "2px 10px", "borderRadius": "10px",
                                     "marginLeft": "10px"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
        html.P([html.Strong(f"{rating}: ", style={"color": pal["dot"]}), why,
                "  Click any card to open its tab."],
               style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
    ]


def _execsum(metrics):
    """Executive summary block — rebuilt live on data refresh."""
    cq = metrics["latest_quarter"]
    gov = get_q(metrics, cq).get("governance") or {}
    return [
        html.Div(f"Executive Summary (Port 2025 — {q_label(cq)})", style=SECTION_TITLE),
        html.Div(gov.get("exec_summary") or "Run the pipeline to generate summary.",
                 style={"fontSize": "13px", "lineHeight": "1.6", "color": "#334155"}),
    ]


def layout(metrics: dict):
    # Header, exec summary, cards, scorecard and sparklines are all filled by
    # callbacks keyed on the data-version store, so the Update-data button
    # refreshes the WHOLE page instantly. Only the static controls live here.
    bar = sticky_bar([compare_selector(
        TAB, within_label="Within-Portfolio (now + since last quarter)",
        cross_label="Cross-Portfolio (Port 2024 vs Port 2025)", default="within")],
        summary_id=f"dqd-{TAB}-summary")

    return [
        _data_bar(metrics),
        html.Div(id=f"dqd-{TAB}-header", style=SECTION),
        bar,
        html.Div(id=f"dqd-{TAB}-execsum", style=SECTION),

        # Priority worklist (governance issues + recommendations) intentionally
        # not rendered yet — re-enable `_worklist(metrics),` here once those are
        # AI-backed rather than placeholder. Helper kept below for that.

        html.Div(id=f"dqd-{TAB}-cards",
                 style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
                        "gap": "12px", "marginBottom": "6px"}),
        html.Div(SEV_NOTE, style=dict(MUTED, marginBottom="16px")),

        html.Div(id=f"dqd-{TAB}-scorecard"),
        html.Div(id=f"dqd-{TAB}-spark"),
    ]


def register_callbacks(app, metrics: dict, as_pages: bool = False):

    @app.callback(
        Output(f"dqd-{TAB}-cards", "children"),
        Output(f"dqd-{TAB}-scorecard", "children"),
        Output(f"dqd-{TAB}-summary", "children"),
        Input(f"dqd-{TAB}-compare", "value"),
        Input(f"dqd-{TAB}-data-version", "data"),
    )
    def _mode(compare, _ver):
        cross = compare == "cross"
        cards = [_card(s, cross, as_pages) for s in _domain_specs(metrics)]
        if cross:
            sc = metrics.get("scorecard") or {}
            summary = html.Span([
                "Showing ", html.Strong("Cross-Portfolio"),
                f" — Port 2024 ({sc.get('quarter_24') or 'P24'}) vs Port 2025 "
                f"({sc.get('quarter_25') or 'P25'}). Cards without a portfolio-level "
                "cross metric point to their tab's own Cross view."])
            return cards, _scorecard_section(metrics), summary
        summary = html.Span([
            "Showing ", html.Strong("Within-Portfolio"),
            f" — Port 2025 current snapshot ({q_label(metrics['latest_quarter'])}) "
            "with change since last quarter. Click any card to open its tab."])
        return cards, html.Div(), summary

    @app.callback(
        Output(f"dqd-{TAB}-header", "children"),
        Output(f"dqd-{TAB}-execsum", "children"),
        Output(f"dqd-{TAB}-spark", "children"),
        Input(f"dqd-{TAB}-data-version", "data"),
    )
    def _data_render(_ver):
        # Data-only panels (independent of the Within/Cross toggle); re-render
        # on refresh via the version bump.
        return _header(metrics), _execsum(metrics), _spark_strip(metrics)

    @app.callback(
        Output(f"dqd-{TAB}-data-status", "children"),
        Output(f"dqd-{TAB}-data-version", "data"),
        Input(f"dqd-{TAB}-refresh", "n_clicks"),
        State(f"dqd-{TAB}-data-version", "data"),
        prevent_initial_call=True,
    )
    def _refresh(_n, ver):
        # Rebuild from the configured source and swap the result into `metrics`
        # in place, so every page/callback holding this dict sees the new data.
        from .. import data_access as dq_data
        try:
            dq_data.recompute_into(metrics)
        except Exception as e:  # surface the failure instead of a stuck spinner
            return f"Update failed: {e}", ver or 0
        return _data_status(metrics), (ver or 0) + 1

    if as_pages:
        return  # STATpy: cards are page links; no internal dcc.Tabs to drive

    @app.callback(
        Output("dqd-main-tabs", "value"),
        Input({"type": "dqd-ov-card", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _navigate(clicks):
        if not ctx.triggered_id or not any(clicks or []):
            raise PreventUpdate
        return ctx.triggered_id["index"]
