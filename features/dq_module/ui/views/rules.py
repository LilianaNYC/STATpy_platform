"""Business Rules & Governance tab — port of pages/business_rules_page.py.

Operational rule failures, anomaly indicators, and the governance layer
(exec summary, materiality grid, RCA / impact / tracker / recommendations).
The failure-rate trend chart honors the comparison mode bar; everything else
is a snapshot of the latest quarter.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import Output, dcc, html

from ..common import (
    GRAPH_CFG, GRID2, P24_COLOR, SECTION, SECTION_IN_GRID, SECTION_TITLE,
    arrow_delta, badge, cmp_filter, cmp_layout, cmp_traces, cmp_x, fig, fmt,
    fmt_b, fmt_n, get_q, kpi_card, kpi_grid, lens_chip, lens_label, mode_bar,
    mode_inputs, pct, q_label, register_mode_bar, simple_table, td,
)

TAB = "rules"

SEV_DOT = {"Critical": "#dc2626", "High": "#ea580c", "Medium": "#d97706", "Low": "#16a34a"}


def _sev_map(by_rule):
    sev = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for r in by_rule:
        if not r.get("passed"):
            sev[r.get("severity")] = sev.get(r.get("severity"), 0) + (r.get("failed_records") or 0)
    return sev


def _materiality_grid(issues):
    cell_bg = [
        ["#fef9c3", "#fef08a", "#fde047"],
        ["#fef08a", "#fde047", "#fdba74"],
        ["#fde047", "#fdba74", "#fca5a5"],
    ]
    pos_map = {"Low": 0, "Medium": 1, "High": 2}
    cell_map = {}
    for i, iss in enumerate(issues):
        col = pos_map.get(iss.get("likelihood"), 1)
        row = pos_map.get(iss.get("business_impact"), 1)
        cell_map.setdefault((row, col), []).append({"idx": i + 1, "sev": iss.get("severity")})

    def issue_dot(idx, sev, size=22):
        return html.Span(str(idx), style={
            "display": "inline-flex", "alignItems": "center", "justifyContent": "center",
            "width": f"{size}px", "height": f"{size}px", "borderRadius": "50%",
            "background": SEV_DOT.get(sev, "#6b7280"), "color": "#fff",
            "fontSize": "10px", "fontWeight": "700", "margin": "2px"})

    def mat_cell(row, col):
        items = cell_map.get((row, col), [])
        return html.Td([issue_dot(it["idx"], it["sev"]) for it in items],
                       style={"background": cell_bg[row][col], "verticalAlign": "middle",
                              "textAlign": "center", "padding": "8px",
                              "border": "1px solid #e2e8f0", "minWidth": "80px",
                              "height": "52px"})

    axis_th = {"padding": "4px 8px", "fontWeight": "700", "color": "#64748b",
               "border": "1px solid #e2e8f0", "textAlign": "center", "fontSize": "10px"}
    grid = html.Table([
        html.Tbody([
            html.Tr([html.Th("High", style=axis_th), mat_cell(2, 0), mat_cell(2, 1), mat_cell(2, 2)]),
            html.Tr([html.Th("Med", style=axis_th), mat_cell(1, 0), mat_cell(1, 1), mat_cell(1, 2)]),
            html.Tr([html.Th("Low", style=axis_th), mat_cell(0, 0), mat_cell(0, 1), mat_cell(0, 2)]),
            html.Tr([html.Td(""),
                     html.Th("Low", style=axis_th), html.Th("Medium", style=axis_th),
                     html.Th("High", style=axis_th)]),
            html.Tr(html.Td("LIKELIHOOD →  (rows = BUSINESS IMPACT)", colSpan=4,
                            style={"textAlign": "center", "color": "#64748b",
                                   "fontSize": "10px", "fontWeight": "700",
                                   "letterSpacing": ".05em", "paddingTop": "4px"})),
        ])
    ], style={"borderCollapse": "collapse", "fontSize": "11px"})

    legend_rows = [html.Tr([
        td(issue_dot(i + 1, iss.get("severity"), size=20), width="28px"),
        td(iss.get("name"), fontSize="10px"),
        td(badge(iss.get("severity"))),
    ]) for i, iss in enumerate(issues[:10])]
    legend = simple_table(["#", "Issue", "Sev"], legend_rows)

    return html.Div([grid, html.Div(legend, style={"flex": "1", "minWidth": "180px"})],
                    style={"display": "flex", "gap": "16px", "alignItems": "flex-start",
                           "flexWrap": "wrap"})


def layout(metrics: dict):
    cq = metrics["latest_quarter"]
    pq = metrics.get("prior_quarter")
    d = get_q(metrics, cq)
    pd_ = get_q(metrics, pq)
    rules_ = d.get("business_rules") or {}
    prul = pd_.get("business_rules") or {}
    tech = d.get("tech_dq") or {}
    recon = tech.get("reconciliation") or {}
    gov = d.get("governance") or {}
    rating = gov.get("dq_rating") or "GREEN"
    issues = gov.get("issues") or []
    by_rule = rules_.get("by_rule") or []
    sev_map = _sev_map(by_rule)
    sev_total = sum(sev_map.values()) or 1

    header = html.Div([
        html.H2(f"Business Rules & Governance — {q_label(cq)}",
                style={"margin": "0 0 6px", "fontSize": "20px"}),
        html.P("Operational rule failures, anomaly indicators, and governance "
               "interpretation (exec summary, materiality, recommendations).",
               style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
    ], style=SECTION)

    rating_pal = {"GREEN": ("#dcfce7", "#166534", "✅"),
                  "MODERATE": ("#fef3c7", "#92400e", "⚠️"),
                  "RED": ("#fee2e2", "#991b1b", "🚨")}.get(rating, ("#f3f4f6", "#374151", ""))
    summary_card = html.Div([
        html.Div([
            html.Div([
                html.Div("Executive Summary (AI-Generated)", style=SECTION_TITLE),
                html.Div(gov.get("exec_summary") or "—",
                         style={"fontSize": "13px", "lineHeight": "1.6", "color": "#334155"}),
            ], style={"flex": "1", "minWidth": "280px"}),
            html.Div([
                html.Div("DQ Rating", style={"fontSize": "10px", "color": "#64748b",
                                             "fontWeight": "700", "textTransform": "uppercase",
                                             "marginBottom": "8px"}),
                html.Div(f"{rating_pal[2]} {rating}",
                         style={"fontSize": "15px", "fontWeight": "800",
                                "background": rating_pal[0], "color": rating_pal[1],
                                "padding": "8px 16px", "borderRadius": "10px"}),
                html.Div("vs prior quarter", style={"fontSize": "10px", "color": "#64748b",
                                                    "marginTop": "8px"}),
            ], style={"textAlign": "center", "padding": "16px", "background": "#f3f4f6",
                      "borderRadius": "10px", "minWidth": "140px"}),
        ], style={"display": "flex", "alignItems": "flex-start", "gap": "16px",
                  "flexWrap": "wrap"}),
    ], style=SECTION)

    rf_delta = None
    if rules_.get("rules_failed") is not None:
        rf_delta = arrow_delta(-(rules_.get("rules_failed", 0) - (prul.get("rules_failed") or 0)))
    kpis = kpi_grid([
        kpi_card("Total Rules Executed", fmt_n(rules_.get("total_executed")), icon="📋"),
        kpi_card("Rules Failed", fmt_n(rules_.get("rules_failed")), icon="❌", delta=rf_delta),
        kpi_card("Critical Failures", fmt_n(rules_.get("critical_failures")), icon="🚨"),
        kpi_card("Records Failed", fmt_n(rules_.get("records_failed")), icon="🗄️"),
        kpi_card("Failure Rate %", pct(rules_.get("failure_rate_pct"), 2), icon="📉"),
        kpi_card("Rules Passed", fmt_n(rules_.get("rules_passed")), icon="✅"),
    ], 6)

    anomaly_kpis = kpi_grid([
        kpi_card("MANUAL Balance Source", fmt_n(tech.get("manual_count")),
                 "balance not from system", icon="🖊️"),
        kpi_card("Negative ALLL", fmt_n(tech.get("alll_negative_count")),
                 "sign-convention errors (BR_011)", icon="📉"),
        kpi_card("RWA Excluded (Flag=N)", fmt_n(tech.get("rwa_exclusion_count")),
                 f"{fmt_n(tech.get('rwa_inclusion_count'))} included", icon="🚫"),
        kpi_card("Capital Charge = 0", fmt_n(tech.get("capital_charge_zero_count")),
                 "when RWA flag = Y (CF_002)", icon="💰"),
    ], 4)

    donut = go.Figure()
    sev_vals = [sev_map.get(s, 0) for s in ("Critical", "High", "Medium", "Low")]
    if any(sev_vals):
        donut.add_trace(go.Pie(values=sev_vals,
                               labels=["Critical", "High", "Medium", "Low"], hole=0.6,
                               marker={"colors": ["#dc2626", "#ea580c", "#d97706", "#16a34a"]},
                               textinfo="none",
                               hovertemplate="%{label}: %{value}<extra></extra>"))
    donut.update_layout(margin={"t": 5, "r": 5, "b": 5, "l": 5}, height=180,
                        paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    sev_table = simple_table(
        ["Severity", "Failed Records", "%"],
        [html.Tr([td(badge(s)), td(fmt_n(sev_map.get(s, 0))),
                  td(pct(sev_map.get(s, 0) / sev_total * 100))])
         for s in ("Critical", "High", "Medium", "Low")])

    top_rules = sorted(by_rule, key=lambda r: -(r.get("failure_rate_pct") or 0))[:10]
    top_rows = [html.Tr([
        td(str(i + 1), fontWeight="700"),
        td(r.get("code"), fontFamily="monospace"),
        td(r.get("description"), fontSize="11px"),
        td(badge(r.get("severity"))),
        td(fmt_n(r.get("failed_records")), fontWeight="600",
           color="#16a34a" if r.get("passed") else "#dc2626"),
        td(pct(r.get("failure_rate_pct")),
           color="#16a34a" if r.get("passed") else "#dc2626"),
        td(badge("Resolved" if r.get("passed") else "Open")),
    ]) for i, r in enumerate(top_rules)]

    issue_rows = [html.Tr([
        td(str(i + 1)), td(iss.get("name")), td(badge(iss.get("severity"))),
        td(fmt_n(iss.get("affected_records"))), td(pct(iss.get("affected_pct"))),
        td(iss.get("use_cases"), fontSize="11px", color="#64748b"),
    ]) for i, iss in enumerate(issues[:10])]

    rca_rows = [html.Tr([td(iss.get("name")),
                         td(iss.get("root_cause"), fontSize="11px", color="#64748b")])
                for iss in issues[:8]]
    impact_rows = [html.Tr([td(iss.get("name")), td(badge(iss.get("severity"))),
                            td(iss.get("impact"), fontSize="11px", color="#64748b")])
                   for iss in issues[:8]]
    tracker_rows = [html.Tr([td(iss.get("name")), td(iss.get("owner")),
                             td(badge(iss.get("status"))), td(iss.get("opened_date")),
                             td(iss.get("target_date")), td("0")])
                    for iss in issues[:8]]
    rec_rows = [html.Tr([td(r.get("text"), fontSize="12px"), td(badge(r.get("priority"))),
                         td(r.get("owner")), td(r.get("eta"))])
                for r in (gov.get("recommendations") or [])]

    seg_rows = []
    for s in sorted(rules_.get("by_segment") or [],
                    key=lambda x: -(x.get("failure_rate_pct") or 0)):
        bar_w = min(100, (s.get("failure_rate_pct") or 0) * 10)
        seg_rows.append(html.Tr([
            td(s.get("segment")),
            td(html.Div(html.Div(style={"background": "#dc2626", "borderRadius": "4px",
                                        "height": "10px", "width": f"{bar_w}%"}),
                        style={"background": "#f3f4f6", "borderRadius": "4px",
                               "height": "10px", "maxWidth": "120px"})),
            td(pct(s.get("failure_rate_pct")), color="#dc2626"),
        ]))
    dom_rows = [html.Tr([
        td(r.get("domain")), td(fmt_n(r.get("failed_records"))),
        td(pct(r.get("failure_rate_pct")),
           color="#dc2626" if (r.get("failure_rate_pct") or 0) > 1 else "#0f172a"),
    ]) for r in (rules_.get("by_domain") or [])]

    crit_rows = [html.Tr([
        td(r.get("code"), fontFamily="monospace"), td(r.get("description"), fontSize="11px"),
        td(r.get("detected_on")), td(r.get("segment")), td(fmt_n(r.get("affected_records"))),
        td(badge(r.get("status"))), td(r.get("assigned_to")), td(r.get("last_updated")),
    ]) for r in (rules_.get("recent_critical") or [])]

    wf = go.Figure()
    if recon:
        wf.add_trace(go.Waterfall(
            x=["Source System Total", "Timing Diff", "Mapping Diff", "Adjustments", "DQ Total"],
            y=[recon.get("source_total"), recon.get("timing_diff"),
               recon.get("mapping_diff"), recon.get("adjustment"), recon.get("dq_total")],
            measure=["absolute", "relative", "relative", "relative", "total"],
            text=[fmt_b(recon.get("source_total")), fmt_b(recon.get("timing_diff")),
                  fmt_b(recon.get("mapping_diff")), fmt_b(recon.get("adjustment")),
                  fmt_b(recon.get("dq_total"))],
            textposition="outside",
            connector={"line": {"color": "#e5e7eb"}},
            increasing={"marker": {"color": "#16a34a"}},
            decreasing={"marker": {"color": "#dc2626"}},
            totals={"marker": {"color": "#2563eb"}}))
    wf.update_layout(margin={"t": 10, "r": 40, "b": 60, "l": 40}, height=240,
                     paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                     yaxis={"title": "USD Billions", "gridcolor": "#f1f5f9"},
                     showlegend=False)

    def card(title, *kids, in_grid=True):
        return html.Div([html.Div(title, style=SECTION_TITLE), *kids],
                        style=SECTION_IN_GRID if in_grid else SECTION)

    label_style = {"fontSize": "10px", "fontWeight": "700", "color": "#64748b",
                   "textTransform": "uppercase", "letterSpacing": ".05em",
                   "marginBottom": "6px"}

    return [
        header,
        summary_card,
        html.Div("Rule Execution", style=label_style), kpis,
        html.Div("Data Anomaly Indicators", style=label_style), anomaly_kpis,
        mode_bar(TAB, metrics),
        html.Div([
            html.Div([
                html.Div(["Rule Failure Rate % Over Time ",
                          html.Span(id=f"dqd-{TAB}-lens")], style=SECTION_TITLE),
                dcc.Graph(id=f"dqd-{TAB}-chart-trend", config=GRAPH_CFG),
            ], style=SECTION_IN_GRID),
            card("Failures by Severity (by Failed Records)",
                 html.Div([dcc.Graph(figure=donut, config=GRAPH_CFG,
                                     style={"minWidth": "180px"}),
                           html.Div(sev_table, style={"flex": "1"})],
                          style={"display": "flex", "gap": "12px",
                                 "alignItems": "center"})),
        ], style=GRID2),
        html.Div([
            card("Top Failed Business Rules (Top 10)",
                 simple_table(["#", "Code", "Rule Description", "Severity",
                               "Failed Records", "Failure Rate %", "Status"], top_rows)
                 if top_rows else html.Div("✅ All rules passed",
                                           style={"color": "#16a34a", "fontSize": "12px",
                                                  "padding": "8px"})),
            card("Top DQ Issues (by Severity)",
                 simple_table(["#", "Issue", "Severity", "Affected", "%", "Use Cases"],
                              issue_rows)
                 if issue_rows else html.Div("✅ No significant issues this quarter",
                                             style={"color": "#16a34a", "fontSize": "12px",
                                                    "padding": "8px"})),
        ], style=GRID2),
        card("Materiality Heat Map",
             html.Div("Each numbered badge corresponds to an issue from the table above, "
                      "plotted by likelihood × business impact.",
                      style={"fontSize": "11px", "color": "#64748b", "marginBottom": "10px"}),
             _materiality_grid(issues), in_grid=False),
        html.Div([
            card("Root Cause Analysis (AI-Assisted)",
                 simple_table(["Issue", "Likely Root Cause"], rca_rows) if rca_rows
                 else html.Div("No issues to analyze.", style={"color": "#94a3b8",
                                                               "fontSize": "12px"})),
            card("Business Impact Assessment",
                 simple_table(["Issue", "Severity", "Potential Impact"], impact_rows)
                 if impact_rows else html.Div("✅ No material impacts identified.",
                                              style={"color": "#16a34a", "fontSize": "12px"})),
        ], style=GRID2),
        card("Issue Tracker",
             simple_table(["Issue", "Owner", "Status", "Opened", "Target Resolution",
                           "Days Open"], tracker_rows)
             if tracker_rows else html.Div("No open issues.",
                                           style={"color": "#94a3b8", "fontSize": "12px"}),
             in_grid=False),
        html.Div([
            card("Failures by Business Segment",
                 simple_table(["Segment", "Failure Rate", "%"], seg_rows)),
            card("Failures by Data Domain",
                 simple_table(["Domain", "Failed Records", "Failure Rate %"], dom_rows)),
        ], style=GRID2),
        card("Recent Critical Failures",
             simple_table(["Code", "Rule", "Detected On", "Segment", "Affected Records",
                           "Status", "Assigned To", "Last Updated"], crit_rows)
             if crit_rows else html.Div("✅ No critical failures this quarter",
                                        style={"color": "#16a34a", "fontSize": "12px",
                                               "padding": "8px"}),
             in_grid=False),
        card("Balance Reconciliation Waterfall (USD Billions)",
             html.Div("Source-system total → adjustments (timing, mapping, manual) → "
                      "reported DQ total.",
                      style={"fontSize": "11px", "color": "#64748b", "marginBottom": "8px"}),
             dcc.Graph(figure=wf, config=GRAPH_CFG) if recon
             else html.Div("Reconciliation data not available.",
                           style={"color": "#94a3b8", "fontSize": "12px",
                                  "padding": "16px"}),
             in_grid=False),
        html.Div([
            card("Recommended Actions (AI-Generated)",
                 simple_table(["Recommendation", "Priority", "Owner", "ETA"], rec_rows)
                 if rec_rows else html.Div("No recommendations generated.",
                                           style={"color": "#94a3b8", "fontSize": "12px"})),
            card("Governance Commentary (AI-Draft)",
                 html.Div([
                     f"Based on the current snapshot ({q_label(cq)}), the portfolio data "
                     f"quality is rated ", html.Strong(rating),
                     ". The primary concerns are rule failures in credit risk and "
                     "collateral data domains. Monitoring frequency: ",
                     html.Strong("Quarterly"),
                     " with ad-hoc review triggered by PSI > 0.20 on any key variable. "
                     "Suggested model owner action: validate LGD and PD inputs against "
                     "source systems before next ECL run.",
                 ], style={"fontSize": "13px", "lineHeight": "1.6", "color": "#334155"})),
        ], style=GRID2),
    ]


def register_callbacks(app, metrics: dict):
    register_mode_bar(app, TAB)

    @app.callback(
        Output(f"dqd-{TAB}-chart-trend", "figure"),
        Output(f"dqd-{TAB}-lens", "children"),
        *mode_inputs(TAB),
    )
    def _trend(mode, cq, pq, hist_start, hist_end):
        mode = mode or "historical"
        traces = cmp_traces(metrics, "failure_rate_over_time", "failure_rate_pct",
                            mode, hist_start, hist_end,
                            color24=P24_COLOR, color25="#dc2626")
        a25 = cmp_filter((metrics.get("time_series") or {}).get("failure_rate_over_time"),
                         mode, hist_start, hist_end)
        if a25:
            x = cmp_x(a25, mode)
            traces.append(go.Scatter(x=x, y=[1.0] * len(x), name="Target 1%",
                                     mode="lines",
                                     line={"color": "#6b7280", "width": 1, "dash": "dot"}))
        return (fig(traces, cmp_layout("%", 200)),
                lens_chip(lens_label(metrics, mode, cq, pq, hist_start, hist_end), mode))
