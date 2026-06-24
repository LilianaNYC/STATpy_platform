"""Population tab — port of pages/population_page.py.

Population movements + churn + segment composition + the Retained Portfolio
CRR Migration analysis. The CRR Migration Matrix is clickable (dcc.Store of
"from|to" grade keys); a non-empty selection switches the Key Columns sample
table to the precomputed `crr_facility_sample`, filtered by its
`_crr_transition` tag (gotcha #8: never recompute the representative rows).
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from ..common import (
    GRAPH_CFG, GRID2, P24_COLOR, P25_COLOR, SECTION, SECTION_IN_GRID,
    SECTION_TITLE, active_filter_chip, apply_filter_controls, cmp_filter,
    cmp_layout, cmp_traces, compare_selector, empty_note, fig, fmt, fmt_n,
    get_q, kpi_card, kpi_grid, line_trace, pct, q_label, simple_table,
    sticky_bar, td,
)

TAB = "population"

SEG_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
              "#0891b2", "#db2777", "#65a30d", "#6b7280"]


def _bal_str(v):
    v = v or 0
    return ("+$" + fmt(v, 1) + "M") if v >= 0 else ("-$" + fmt(-v, 1) + "M")


# ── CRR migration matrix ──────────────────────────────────────────────────

def _crr_matrix_component(mig, selection):
    grades = mig.get("grades") or []
    M = mig.get("matrix") or {}
    if not grades:
        return empty_note("No retained-facility data available for this quarter pair.")
    sel = set(selection or [])

    max_count = 0
    for f in grades:
        for t in grades:
            if f != t:
                max_count = max(max_count, ((M.get(f) or {}).get(t) or {}).get("count") or 0)

    def cell(f, t):
        c = (M.get(f) or {}).get(t) or {"count": 0, "balance": 0}
        n = c.get("count") or 0
        if n == 0:
            return html.Td("—", style={"textAlign": "center", "color": "#cbd5e1",
                                       "fontSize": "11px",
                                       "border": "1px solid #f1f5f9"})
        ff, tt = float(f), float(t)
        if ff == tt:
            bg, fg = "rgba(99,102,241,0.18)", "#3730a3"
        else:
            intensity = min(1.0, n / max_count) if max_count else 0
            alpha = 0.15 + intensity * 0.55
            if tt < ff:
                bg = f"rgba(22,163,74,{alpha:.2f})"
                fg = "#fff" if intensity > 0.4 else "#14532d"
            else:
                bg = f"rgba(220,38,38,{alpha:.2f})"
                fg = "#fff" if intensity > 0.4 else "#7f1d1d"
        key = f"{f}|{t}"
        selected = key in sel
        content = [str(n)]
        if selected:
            content.append(html.Div("SELECTED", style={"fontSize": "8px",
                                                       "color": "#9a3412",
                                                       "fontWeight": "700"}))
        return html.Td(html.Button(
            content, id={"type": "dqd-pop-crr", "index": key}, n_clicks=0,
            title=(f"From CRR {f} → {t}: {n} facilities ({_bal_str(c.get('balance'))}). "
                   "Click to toggle this transition in the drilldown."),
            style={"width": "100%", "background": bg, "color": fg,
                   "textAlign": "center", "fontWeight": "600", "padding": "6px",
                   "cursor": "pointer",
                   "border": "3px solid #9a3412" if selected else "1px solid #fff"}),
            style={"padding": 0})

    th = {"background": "#1e293b", "color": "#fff", "fontSize": "11px",
          "textAlign": "center", "padding": "6px 2px", "border": "1px solid #fff"}
    header = html.Tr([html.Th("From \\ To", style=dict(th, background="#0f1d35",
                                                       fontSize="10px", width="62px"))] +
                     [html.Th(g, style=th) for g in grades])
    body = [html.Tr([html.Th(f, style=dict(th, textAlign="right"))] +
                    [cell(f, t) for t in grades]) for f in grades]

    legend = html.Div([
        html.Span([html.Span(style={"display": "inline-block", "width": "14px",
                                    "height": "14px",
                                    "background": "rgba(22,163,74,0.55)",
                                    "borderRadius": "2px", "marginRight": "6px",
                                    "verticalAlign": "middle"}),
                   "Upgrade (better grade)"]),
        html.Span([html.Span(style={"display": "inline-block", "width": "14px",
                                    "height": "14px",
                                    "background": "rgba(99,102,241,0.18)",
                                    "borderRadius": "2px", "marginRight": "6px",
                                    "verticalAlign": "middle"}),
                   "No change (diagonal)"]),
        html.Span([html.Span(style={"display": "inline-block", "width": "14px",
                                    "height": "14px",
                                    "background": "rgba(220,38,38,0.55)",
                                    "borderRadius": "2px", "marginRight": "6px",
                                    "verticalAlign": "middle"}),
                   "Downgrade (worse grade)"]),
        html.Span("Click any cell to toggle the drilldown",
                  style={"color": "#9a3412", "fontWeight": "500"}),
    ], style={"marginTop": "10px", "fontSize": "10px", "color": "#64748b",
              "display": "flex", "gap": "14px", "flexWrap": "wrap"})

    return html.Div([
        html.Div(html.Table([html.Thead(header), html.Tbody(body)],
                            style={"borderCollapse": "collapse", "fontSize": "11px",
                                   "tableLayout": "fixed", "width": "100%",
                                   "minWidth": "560px"}),
                 style={"overflowX": "auto"}),
        legend,
    ])


def _crr_selection_stats(mig, selection):
    if not selection:
        return None
    M = mig.get("matrix") or {}
    tot_fac, tot_bal, up_n, dn_n, diag_n = 0, 0.0, 0, 0, 0
    items = []
    for key in selection:
        f, t = key.split("|")
        c = (M.get(f) or {}).get(t) or {"count": 0, "balance": 0}
        tot_fac += c.get("count") or 0
        tot_bal += c.get("balance") or 0
        if float(f) == float(t):
            diag_n += c.get("count") or 0
        elif float(t) < float(f):
            up_n += c.get("count") or 0
        else:
            dn_n += c.get("count") or 0
        items.append((f, t, c.get("count") or 0))
    items.sort(key=lambda x: (float(x[0]), float(x[1])))

    def dot(color):
        return html.Span(style={"display": "inline-block", "width": "10px",
                                "height": "10px", "background": color,
                                "borderRadius": "50%", "marginRight": "5px",
                                "verticalAlign": "middle"})

    chips = [html.Span(f"{f} → {t} · {n}", style={
        "display": "inline-block", "fontSize": "10px", "fontFamily": "monospace",
        "color": "#475569", "background": "#fff", "border": "1px solid #e2e8f0",
        "borderRadius": "10px", "padding": "1px 8px", "marginRight": "4px"})
        for f, t, n in items[:8]]
    more = f" +{len(items) - 8} more" if len(items) > 8 else ""

    return html.Div([
        html.Div([
            html.Span("Selection drilldown", style={"fontSize": "10px",
                                                    "fontWeight": "700",
                                                    "color": "#9a3412",
                                                    "textTransform": "uppercase",
                                                    "letterSpacing": ".05em"}),
            html.Span([html.Strong(str(len(selection))), " transition(s) · ",
                       html.Strong(fmt_n(tot_fac)), " facilit(ies) · ",
                       html.Strong(_bal_str(tot_bal),
                                   style={"color": "#16a34a" if tot_bal >= 0
                                          else "#dc2626"}),
                       " balance change"],
                      style={"fontSize": "11px", "color": "#475569",
                             "marginLeft": "10px"}),
        ], style={"marginBottom": "8px"}),
        html.Div([
            html.Span([dot("#16a34a"), html.Strong(fmt_n(up_n)), " upgrades"]),
            html.Span([dot("#6366f1"), html.Strong(fmt_n(diag_n)), " no-change"]),
            html.Span([dot("#dc2626"), html.Strong(fmt_n(dn_n)), " downgrades"]),
        ], style={"display": "flex", "gap": "14px", "fontSize": "11px",
                  "color": "#475569", "marginBottom": "6px"}),
        html.Div(chips + ([html.Span(more, style={"fontSize": "10px",
                                                  "color": "#94a3b8"})] if more else []),
                 style={"lineHeight": "1.8"}),
    ], style={"background": "#fafafa", "border": "1px solid #e2e8f0",
              "borderLeft": "3px solid #9a3412", "borderRadius": "6px",
              "padding": "10px 12px", "marginBottom": "10px"})


# ── Key columns sample table ──────────────────────────────────────────────

def _sample_section(metrics, selection):
    sel_active = bool(selection)
    if sel_active:
        sample = metrics.get("crr_facility_sample") or {}
        cols = sample.get("columns") or []
        sel = set(selection)
        rows_all = [r for r in (sample.get("rows") or [])
                    if r.get("_crr_transition") in sel]
        title_suffix = " — filtered to CRR selection"
        desc = (f"Retained facilities (FCL-ID present in both "
                f"{q_label(sample.get('prior_q'))} and {q_label(sample.get('current_q'))}) "
                "whose CRR transition matches the cells selected in the matrix above.")
    else:
        sample = metrics.get("key_sample_rows") or {}
        cols = sample.get("columns") or []
        rows_all = sample.get("rows") or []
        title_suffix = ""
        desc = (f"Pandas-style preview: the first {len(rows_all)} rows of the latest "
                "quarter's dataframe restricted to the schema-flagged key variables.")

    if not cols:
        return html.Div([html.Div("Key Columns — Sample Records", style=SECTION_TITLE),
                         empty_note("No sample columns available.")])

    if sel_active and not rows_all:
        return html.Div([
            html.Div(f"Key Columns — Sample Records{title_suffix}", style=SECTION_TITLE),
            html.Div("No retained facilities in the sample match the selected "
                     "transition(s). The sample stratifies up to 5 facilities per matrix "
                     "cell, so this should be rare.",
                     style={"padding": "24px", "color": "#92400e",
                            "background": "#fffbeb", "border": "1px solid #fcd34d",
                            "borderRadius": "6px", "fontSize": "12px",
                            "textAlign": "center"}),
        ])

    # Column types over the full set (so formatting is consistent across pages)
    is_numeric = []
    for c in cols:
        seen, numeric = False, True
        for r in rows_all:
            v = r.get(c)
            if v is None:
                continue
            seen = True
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                numeric = False
                break
        is_numeric.append(seen and numeric)
    numeric_cols = {c for c, num in zip(cols, is_numeric) if num}

    def fmt_cell(v, num):
        if v is None:
            return "—"
        if num:
            try:
                fv = float(v)
                return fmt_n(fv) if fv == int(fv) else fmt(fv, 3)
            except (TypeError, ValueError):
                return str(v)
        return str(v)

    # DataTable columns: # index, optional CRR transition, then the key columns
    table_cols = [{"name": "#", "id": "_idx"}]
    if sel_active:
        table_cols.append({"name": "CRR Transition", "id": "_crr"})
    table_cols += [{"name": c, "id": c} for c in cols]

    data = []
    for i, r in enumerate(rows_all):
        row = {"_idx": i}
        if sel_active:
            row["_crr"] = str(r.get("_crr_transition") or "—").replace("|", " → ")
        for c, num in zip(cols, is_numeric):
            row[c] = fmt_cell(r.get(c), num)
        data.append(row)

    cell_cond = (
        [{"if": {"column_id": c}, "textAlign": "right", "fontFamily": "monospace"}
         for c in numeric_cols]
        + [{"if": {"column_id": "_idx"}, "width": "44px", "textAlign": "right",
            "fontFamily": "monospace", "color": "#64748b", "backgroundColor": "#f8fafc"}]
        + ([{"if": {"column_id": "_crr"}, "textAlign": "center",
             "fontFamily": "monospace", "fontWeight": "700", "color": "#9a3412",
             "backgroundColor": "#fff7ed", "minWidth": "92px"}] if sel_active else []))

    table = dash_table.DataTable(
        columns=table_cols,
        data=data,
        page_size=20,
        page_action="native",
        sort_action="native",
        style_table={"overflowX": "auto", "border": "1px solid #e2e8f0",
                     "borderRadius": "6px"},
        style_header={"backgroundColor": "#0f1d35", "color": "#fff",
                      "fontWeight": "700", "fontSize": "10px", "whiteSpace": "nowrap",
                      "border": "1px solid #1e293b", "textAlign": "left"},
        style_cell={"fontSize": "11px", "padding": "5px 10px", "fontFamily": "inherit",
                    "border": "1px solid #f1f5f9", "textAlign": "left",
                    "whiteSpace": "nowrap", "maxWidth": "220px", "overflow": "hidden",
                    "textOverflow": "ellipsis", "color": "#0f172a"},
        style_data_conditional=[{"if": {"row_index": "odd"},
                                 "backgroundColor": "#fafafa"}],
        style_cell_conditional=cell_cond,
    )

    n_pages = max(1, -(-len(rows_all) // 20))
    meta = (f"{len(rows_all)} retained facilit(ies) matching {len(selection)} "
            f"selected transition(s) · 20 per page ({n_pages} page(s))"
            if sel_active else
            f"{len(rows_all)} sample rows × {len(cols)} key columns · 20 per page "
            f"· snapshot {q_label(sample.get('quarter'))}")

    return html.Div([
        html.Div([
            html.Div(f"Key Columns — Sample Records{title_suffix}",
                     style=dict(SECTION_TITLE, margin=0)),
            html.Div(meta, style={"fontSize": "11px", "color": "#64748b"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "baseline", "flexWrap": "wrap", "marginBottom": "4px"}),
        html.Div(desc, style={"fontSize": "11px", "color": "#64748b",
                              "marginBottom": "10px"}),
        table,
    ], style={"borderLeft": "3px solid #9a3412", "paddingLeft": "8px"}
        if sel_active else None)


# ── Layout ────────────────────────────────────────────────────────────────

def layout(metrics: dict):
    quarters = metrics.get("quarters") or []
    cq = metrics["latest_quarter"]
    filter_dims = metrics.get("population_filter_dims") or {}
    d = get_q(metrics, cq)
    gov = d.get("governance") or {}
    pop = d.get("population") or {}

    dim_opts = [{"label": (meta.get("label") or dim), "value": dim}
                for dim, meta in filter_dims.items()]

    # Sticky comparison + slice bar (Within / Cross-Portfolio, unified with the
    # other tabs). The slice filter is deferred — it only takes effect when
    # "Apply filter" is clicked; the Within/Cross toggle and the snapshot picker
    # are live.
    snap_opts = [{"label": q_label(q), "value": q} for q in reversed(quarters)]
    bar = sticky_bar([
        compare_selector(TAB, within_label="Within-Portfolio (Port 2025 over time)",
                         cross_label="Cross-Portfolio (Port 2024 vs Port 2025)",
                         default="within"),
        html.Div([
            html.Span("Snapshot", style={"fontSize": "10px", "fontWeight": "700",
                                         "color": "#64748b"}),
            dcc.Dropdown(id=f"dqd-{TAB}-snapshot", options=snap_opts, value=cq,
                         clearable=False, style={"width": "120px", "fontSize": "11px"}),
        ], id=f"dqd-{TAB}-snapshot-wrap",
            style={"display": "flex", "alignItems": "center", "gap": "6px"}),
        html.Div([
            html.Span("Slice", style={"fontSize": "10px", "fontWeight": "700",
                                      "color": "#64748b"}),
            dcc.Dropdown(id=f"dqd-{TAB}-filter-dim", options=dim_opts, value=None,
                         placeholder="Dimension…",
                         style={"width": "160px", "fontSize": "11px"}),
            dcc.Dropdown(id=f"dqd-{TAB}-filter-value", options=[], value=None,
                         placeholder="All",
                         style={"width": "170px", "fontSize": "11px"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "6px"}),
        apply_filter_controls(TAB),
    ], summary_id=f"dqd-{TAB}-summary")

    ret_snap_opts = [{"label": q_label(q), "value": q} for q in reversed(quarters)]

    insights = gov.get("population_insights") or [
        {"text": "Population trend driven by new originations across all segments."},
        {"text": f"PSI stands at {fmt(pop.get('psi') or 0, 2)} "
                 f"({pop.get('psi_label') or '—'})."},
    ]

    return [
        html.Div([
            html.H2(["Population Stability Dashboard — ",
                     html.Span(q_label(cq), id=f"dqd-{TAB}-title-q")],
                    style={"margin": "0 0 6px", "fontSize": "20px"}),
            html.P("Monitor population movements, account lifecycle, and segment "
                   "stability over time.",
                   style={"margin": "0 0 4px", "color": "#64748b", "fontSize": "13px"}),
            html.P(["PSI = Population Stability Index (higher = more shift; "
                    "< 0.1 stable, 0.1–0.25 moderate, > 0.25 significant). "
                    "CRR = Customer Risk Rating (lower grade number = better); "
                    "Imp PD = implied probability of default."],
                   style={"margin": 0, "color": "#94a3b8", "fontSize": "11px"}),
        ], style=SECTION),

        dcc.Store(id=f"dqd-{TAB}-crr-sel", data=[]),
        dcc.Store(id=f"dqd-{TAB}-applied", data={"dim": None, "val": None}),
        bar,
        html.Div(id=f"dqd-{TAB}-kpis"),

        html.Div([
            html.Div(["Total Records Over Time ", html.Span(id=f"dqd-{TAB}-lens")],
                     style=SECTION_TITLE),
            dcc.Graph(id=f"dqd-{TAB}-chart-movement", config=GRAPH_CFG),
        ], style=SECTION),

        html.Div([
            html.Div("Churn Dynamics — New / Continuing / Dropped per Quarter",
                     style=SECTION_TITLE),
            html.Div("New (green) adds growth above the zero line, Dropped (red) extends "
                     "below — net total tracked on the right axis.",
                     style={"fontSize": "11px", "color": "#64748b", "marginBottom": "8px"}),
            dcc.Graph(id=f"dqd-{TAB}-chart-churn", config=GRAPH_CFG),
        ], style=SECTION),

        html.Div([
            html.Div("Segment Composition Over Time (% of Portfolio)",
                     style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-segmix"),
        ], style=SECTION),

        html.Div([
        html.Div([
            html.Div("Retained Portfolio — CRR Migration (independent analysis)",
                     style={"fontSize": "12px", "fontWeight": "800",
                            "color": "#9a3412", "textTransform": "uppercase",
                            "letterSpacing": ".05em", "marginBottom": "4px"}),
            html.Div("This block has its own Snapshot Quarter picker and always "
                     "compares the chosen quarter against its immediate prior "
                     "quarter. It does NOT follow the comparison mode selected "
                     "at the top of the page.",
                     style={"fontSize": "11px", "color": "#7c2d12",
                            "marginBottom": "12px"}),
        ]),
        html.Div([
            html.Div([
                html.Div("CRR Migration Analysis",
                         style=dict(SECTION_TITLE, margin=0)),
                html.Div([
                    html.Span("Snapshot Quarter", style={"fontSize": "10px",
                                                         "color": "#64748b",
                                                         "fontWeight": "700",
                                                         "textTransform": "uppercase"}),
                    dcc.Dropdown(id=f"dqd-{TAB}-ret-snapshot", options=ret_snap_opts,
                                 value=cq, clearable=False,
                                 style={"width": "140px", "fontSize": "11px"}),
                    html.Span("View", style={"fontSize": "10px", "color": "#64748b",
                                             "fontWeight": "700",
                                             "textTransform": "uppercase",
                                             "marginLeft": "10px"}),
                    dcc.Dropdown(id=f"dqd-{TAB}-crr-view", clearable=False,
                                 value="change",
                                 options=[{"label": "↑↓ CRR Change (count)",
                                           "value": "change"},
                                          {"label": "$ Exposure Change ($M)",
                                           "value": "exposure"}],
                                 style={"width": "190px", "fontSize": "11px"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "flexWrap": "wrap",
                      "marginBottom": "14px", "gap": "12px"}),
            html.Div([
                html.Div([
                    html.Div(id=f"dqd-{TAB}-crr-chart-title",
                             style={"fontSize": "12px", "fontWeight": "700",
                                    "color": "#111827", "marginBottom": "10px"}),
                    html.Div(id=f"dqd-{TAB}-crr-chart"),
                ], style={"border": "1px solid #e2e8f0", "borderRadius": "8px",
                          "padding": "14px", "background": "#fff",
                          "minWidth": 0}),
                html.Div([
                    html.Div("Retained Portfolio Summary",
                             style={"fontSize": "12px", "fontWeight": "700",
                                    "color": "#111827", "marginBottom": "4px"}),
                    html.Div("Aggregates over all retained facilities",
                             style={"fontSize": "11px", "color": "#64748b",
                                    "marginBottom": "12px"}),
                    html.Div(id=f"dqd-{TAB}-crr-summary"),
                ], style={"border": "1px solid #e2e8f0", "borderRadius": "8px",
                          "padding": "14px", "background": "#fff",
                          "minWidth": 0, "overflowX": "auto"}),
            ], style={"display": "grid", "gridTemplateColumns": "2fr 1fr",
                      "gap": "16px", "alignItems": "stretch"}),
        ], style=SECTION_IN_GRID),

        html.Div([
            html.Div(id=f"dqd-{TAB}-crr-matrix-title", style=SECTION_TITLE),
            html.Div("Number of retained facilities that moved from each prior CRR grade "
                     "(rows) to each current CRR grade (columns). Diagonal = no change.",
                     style={"fontSize": "11px", "color": "#64748b",
                            "marginBottom": "10px"}),
            html.Div(id=f"dqd-{TAB}-crr-sel-stats"),
            html.Div(id=f"dqd-{TAB}-crr-matrix"),
            html.Button("Clear CRR selection", id=f"dqd-{TAB}-crr-clear", n_clicks=0,
                        style={"marginTop": "10px", "fontSize": "10px",
                               "padding": "3px 10px", "border": "1px solid #9a3412",
                               "background": "#fff", "color": "#9a3412",
                               "borderRadius": "4px", "cursor": "pointer"}),
        ], style=dict(SECTION_IN_GRID, marginTop="14px")),

        html.Div(html.Div(id=f"dqd-{TAB}-sample"),
                 style=dict(SECTION_IN_GRID, marginTop="14px")),

        ], style=dict(SECTION, border="2px solid #fdba74", background="#fffdf9",
                      borderLeft="4px solid #9a3412")),

        html.Div([
            html.Div("Population Stability by Business Segment", style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-seg-table"),
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div(["New vs Dropped Accounts by Reason ",
                          html.Span("· representative split, static — not affected by "
                                    "the comparison mode or slice",
                                    style={"fontSize": "9px", "fontWeight": "500",
                                           "color": "#94a3b8"})], style=SECTION_TITLE),
                html.Div([
                    html.Div([
                        html.Div("Top Reasons — New Accounts",
                                 style={"fontSize": "11px", "fontWeight": "700",
                                        "color": "#16a34a", "marginBottom": "6px"}),
                        *[html.Div([html.Span(r.get("reason")),
                                    html.Span(f"{r.get('pct')}%",
                                              style={"fontWeight": "600",
                                                     "color": "#16a34a"})],
                                   style={"display": "flex",
                                          "justifyContent": "space-between",
                                          "fontSize": "11px", "padding": "4px 0",
                                          "borderBottom": "1px solid #f1f5f9"})
                          for r in (pop.get("new_reasons") or [])],
                    ]),
                    html.Div([
                        html.Div("Top Reasons — Dropped Accounts",
                                 style={"fontSize": "11px", "fontWeight": "700",
                                        "color": "#dc2626", "marginBottom": "6px"}),
                        *[html.Div([html.Span(r.get("reason")),
                                    html.Span(f"{r.get('pct')}%",
                                              style={"fontWeight": "600",
                                                     "color": "#dc2626"})],
                                   style={"display": "flex",
                                          "justifyContent": "space-between",
                                          "fontSize": "11px", "padding": "4px 0",
                                          "borderBottom": "1px solid #f1f5f9"})
                          for r in (pop.get("drop_reasons") or [])],
                    ]),
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                          "gap": "16px"}),
            ], style=SECTION_IN_GRID),
            html.Div([
                html.Div(["Key Insights ",
                          html.Span("· illustrative, static — not affected by the "
                                    "comparison mode or slice",
                                    style={"fontSize": "9px", "fontWeight": "500",
                                           "color": "#94a3b8"})], style=SECTION_TITLE),
                *[html.Div(i.get("text"),
                           style={"fontSize": "12px", "color": "#334155",
                                  "padding": "8px 10px", "background": "#f8fafc",
                                  "borderRadius": "6px", "marginBottom": "6px"})
                  for i in insights],
            ], style=SECTION_IN_GRID),
        ], style=GRID2),
    ]


# ── Callbacks ─────────────────────────────────────────────────────────────

def register_callbacks(app, metrics: dict):
    quarters = metrics.get("quarters") or []
    filter_dims = metrics.get("population_filter_dims") or {}

    @app.callback(
        Output(f"dqd-{TAB}-filter-value", "options"),
        Output(f"dqd-{TAB}-filter-value", "value"),
        Input(f"dqd-{TAB}-filter-dim", "value"),
    )
    def _dim_values(dim):
        if not dim or dim not in filter_dims:
            return [], None
        vals = filter_dims[dim].get("values") or []
        return [{"label": v, "value": v} for v in vals], None

    # ── Deferred apply: the slice only commits to the applied Store on click ──
    @app.callback(
        Output(f"dqd-{TAB}-applied", "data"),
        Output(f"dqd-{TAB}-filter-dim", "value"),
        Output(f"dqd-{TAB}-filter-value", "value", allow_duplicate=True),
        Input(f"dqd-{TAB}-apply", "n_clicks"),
        Input(f"dqd-{TAB}-clear", "n_clicks"),
        State(f"dqd-{TAB}-filter-dim", "value"),
        State(f"dqd-{TAB}-filter-value", "value"),
        prevent_initial_call=True,
    )
    def _apply_slice(apply_n, clear_n, dim, val):
        if ctx.triggered_id == f"dqd-{TAB}-clear":
            return {"dim": None, "val": None}, None, None
        # Apply: a slice needs both a dimension and a value to be meaningful.
        if dim and val:
            return {"dim": dim, "val": val}, dim, val
        return {"dim": None, "val": None}, dim, val

    @app.callback(
        Output(f"dqd-{TAB}-crr-sel", "data"),
        Input({"type": "dqd-pop-crr", "index": ALL}, "n_clicks"),
        Input(f"dqd-{TAB}-crr-clear", "n_clicks"),
        State(f"dqd-{TAB}-crr-sel", "data"),
        prevent_initial_call=True,
    )
    def _toggle_crr(cell_clicks, clear_clicks, sel):
        trig = ctx.triggered_id
        if trig == f"dqd-{TAB}-crr-clear":
            return []
        if not ctx.triggered or not ctx.triggered[0].get("value"):
            raise PreventUpdate
        key = trig["index"] if isinstance(trig, dict) else None
        if not key:
            raise PreventUpdate
        sel = list(sel or [])
        if key in sel:
            sel.remove(key)
        else:
            sel.append(key)
        return sel

    @app.callback(
        Output(f"dqd-{TAB}-kpis", "children"),
        Output(f"dqd-{TAB}-chart-movement", "figure"),
        Output(f"dqd-{TAB}-chart-churn", "figure"),
        Output(f"dqd-{TAB}-segmix", "children"),
        Output(f"dqd-{TAB}-crr-chart-title", "children"),
        Output(f"dqd-{TAB}-crr-chart", "children"),
        Output(f"dqd-{TAB}-crr-summary", "children"),
        Output(f"dqd-{TAB}-crr-matrix-title", "children"),
        Output(f"dqd-{TAB}-crr-sel-stats", "children"),
        Output(f"dqd-{TAB}-crr-matrix", "children"),
        Output(f"dqd-{TAB}-sample", "children"),
        Output(f"dqd-{TAB}-seg-table", "children"),
        Output(f"dqd-{TAB}-lens", "children"),
        Output(f"dqd-{TAB}-title-q", "children"),
        Output(f"dqd-{TAB}-active-chip", "children"),
        Output(f"dqd-{TAB}-summary", "children"),
        Output(f"dqd-{TAB}-snapshot-wrap", "style"),
        Input(f"dqd-{TAB}-compare", "value"),
        Input(f"dqd-{TAB}-snapshot", "value"),
        Input(f"dqd-{TAB}-applied", "data"),
        Input(f"dqd-{TAB}-ret-snapshot", "value"),
        Input(f"dqd-{TAB}-crr-view", "value"),
        Input(f"dqd-{TAB}-crr-sel", "data"),
    )
    def _update(compare, snapshot, applied, ret_snap, crr_view, crr_sel):
        cross = (compare == "cross")
        snapshot = snapshot or metrics["latest_quarter"]
        cq = metrics["latest_quarter"] if cross else snapshot
        d = get_q(metrics, cq)
        full_pop = d.get("population") or {}

        applied = applied or {}
        filt_dim, filt_val = applied.get("dim"), applied.get("val")
        slice_data = None
        if filt_dim and filt_val:
            slice_data = ((full_pop.get("slices") or {}).get(filt_dim) or {}) \
                .get(filt_val)
        filter_active = slice_data is not None
        # The slice is a Port-2025 dimension; cross-portfolio (P24 vs P25) has no
        # per-slice equivalent, so the slice only takes effect Within-Portfolio.
        slice_effective = filter_active and not cross
        pop = slice_data if slice_effective else full_pop

        slice_ts = []
        if slice_effective:
            slice_ts = (((metrics.get("time_series") or {})
                         .get("population_slices") or {})
                        .get(filt_dim) or {}).get(filt_val) or []

        # ── Active-filter chip + sticky summary line ──
        dim_label = ((filter_dims.get(filt_dim) or {}).get("label") or filt_dim
                     if filt_dim else None)
        chip = active_filter_chip(f"{dim_label} = {filt_val}" if filter_active else None)
        if cross:
            cmp_text = ("Cross-Portfolio · Port 2024 vs Port 2025 (latest). KPIs & "
                        "Total Records are cross-portfolio; churn, composition and "
                        "the segment table below are Port 2025 (no cross equivalent)")
            slice_text = (f" · slice {dim_label}={filt_val} ignored (Within-Portfolio only)"
                          if filter_active else "")
        else:
            cmp_text = f"Within-Portfolio · Port 2025 snapshot {q_label(snapshot)}"
            slice_text = (f" · slice {dim_label}={filt_val} "
                          f"({fmt_n(pop.get('total'))} accts)"
                          if slice_effective else " · no slice")
        summary = f"Comparing: {cmp_text}{slice_text}"
        snap_wrap_style = ({"display": "none"} if cross else
                           {"display": "flex", "alignItems": "center", "gap": "6px"})
        lens_text = "Cross-Portfolio" if cross else f"Within · {q_label(snapshot)}"

        # ── KPIs ──
        if cross:
            p25_ts = (metrics.get("time_series") or {}).get("population_over_time") or []
            p24_ts = ((metrics.get("port24") or {}).get("time_series") or {}) \
                .get("population_over_time") or []
            p25_total = p25_ts[-1].get("total") if p25_ts else None
            p24_total = p24_ts[-1].get("total") if p24_ts else None
            diff = (p25_total - p24_total
                    if p25_total is not None and p24_total is not None else None)
            diff_pct = (diff / p24_total * 100) if diff is not None and p24_total else None
            kpis = kpi_grid([
                kpi_card("Port 2024 Accounts", fmt_n(p24_total), "latest snapshot"),
                kpi_card("Port 2025 Accounts", fmt_n(p25_total), "latest snapshot"),
                kpi_card("Net Difference",
                         f"{'+' if (diff or 0) >= 0 else ''}{fmt_n(diff)}",
                         f"{pct(diff_pct)} vs Port 2024" if diff_pct is not None else "",
                         color="#16a34a" if (diff or 0) >= 0 else "#dc2626"),
                kpi_card("Population PSI", fmt(full_pop.get("psi"), 3),
                         full_pop.get("psi_label") or "—"),
            ], 4)
        else:
            net = pop.get("net_change") or 0
            kpis = kpi_grid([
                kpi_card("Total Accounts", fmt_n(pop.get("total")),
                         "in slice" if slice_effective else ""),
                kpi_card("New Accounts", fmt_n(pop.get("new")),
                         f"{pct(pop.get('new_pct'))} of total"),
                kpi_card("Dropped Accounts", fmt_n(pop.get("dropped")),
                         f"{pct(pop.get('dropped_pct'))} of prior total"),
                kpi_card("Continuing Accounts", fmt_n(pop.get("continuing")),
                         f"{pct(pop.get('continuing_pct'))} of total"),
                kpi_card("Net Change", f"{'+' if net >= 0 else ''}{fmt_n(net)}",
                         f"{pct(pop.get('net_change_pct'))} vs prior"),
                (kpi_card("Retention %", pct(pop.get("continuing_pct")),
                          "of prior cohort") if slice_effective else
                 kpi_card("Population PSI", fmt(pop.get("psi"), 3),
                          pop.get("psi_label") or "—")),
            ], 6)

        # ── Total Records over time ──
        if cross:
            movement = fig(cmp_traces(metrics, "population_over_time", "total",
                                      "historical", name24="Port 2024",
                                      name25="Port 2025"),
                           cmp_layout("Records", 240, x_title="Quarter"))
        else:
            src = (slice_ts if slice_effective else
                   (metrics.get("time_series") or {}).get("population_over_time") or [])
            arr = cmp_filter(src, "historical")
            nm = f"Port 2025 — {filt_val}" if slice_effective else "Port 2025"
            movement = fig([go.Scatter(
                x=[r.get("label") for r in arr], y=[r.get("total") for r in arr],
                name=nm, mode="lines+markers",
                line={"color": P25_COLOR, "width": 2}, marker={"size": 3})],
                cmp_layout("Records (sliced)" if slice_effective else "Records",
                           240, x_title="Quarter"))

        # ── Churn dynamics (always Port 2025 — churn has no cross equivalent) ──
        churn_ts = cmp_filter(
            slice_ts if slice_effective else
            (metrics.get("time_series") or {}).get("population_over_time") or [],
            "historical")
        churn_x = [r.get("label") or q_label(r.get("quarter")) for r in churn_ts]
        churn = go.Figure([
            go.Bar(name="New", x=churn_x, y=[r.get("new") or 0 for r in churn_ts],
                   marker={"color": "#16a34a"},
                   hovertemplate="%{x}<br>New: +%{y:,}<extra></extra>"),
            go.Bar(name="Dropped", x=churn_x,
                   y=[-(r.get("dropped") or 0) for r in churn_ts],
                   marker={"color": "#dc2626"},
                   hovertemplate="%{x}<br>Dropped: %{y:,}<extra></extra>"),
            go.Scatter(name="Net total", x=churn_x,
                       y=[r.get("total") or 0 for r in churn_ts], yaxis="y2",
                       mode="lines+markers", line={"color": "#0f1d35", "width": 2},
                       marker={"size": 4},
                       hovertemplate="%{x}<br>Total: %{y:,}<extra></extra>"),
        ])
        churn.update_layout(
            barmode="relative", margin={"t": 20, "r": 70, "b": 70, "l": 60}, height=380,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"tickangle": -45, "tickfont": {"size": 9},
                   "title": {"text": "Quarter", "font": {"size": 10}}},
            yaxis={"title": "Accounts (± net flow)", "gridcolor": "#f1f5f9",
                   "zerolinecolor": "#94a3b8", "zerolinewidth": 1},
            yaxis2={"title": "Total", "overlaying": "y", "side": "right",
                    "showgrid": False},
            legend={"orientation": "h", "y": -0.25, "font": {"size": 10}})

        # ── Segment composition (Port 2025 full history) ──
        filtered_notice = html.Div(
            "Segment composition isn't available per-slice in the payload "
            "(per-slice data covers totals and churn, not segment splits). Clear "
            "the slice to see composition; the KPIs and records trend above do "
            "reflect the applied slice.",
            style={"padding": "24px", "textAlign": "center", "color": "#92400e",
                   "background": "#fef3c7", "borderRadius": "6px", "fontSize": "12px"})
        if slice_effective:
            segmix = filtered_notice
        else:
            q_list = list(quarters)
            seg_mix = {}
            for i, q in enumerate(q_list):
                for s in ((get_q(metrics, q).get("population") or {})
                          .get("by_segment") or []):
                    seg_mix.setdefault(s.get("segment"), [0] * len(q_list))
                    seg_mix[s.get("segment")][i] = s.get("current_accounts") or 0
            x_labels = [q_label(q) for q in q_list]
            mix = go.Figure()
            for i, (seg, vals) in enumerate(seg_mix.items()):
                mix.add_trace(go.Scatter(
                    name=seg, x=x_labels, y=vals, mode="none",
                    stackgroup="one", groupnorm="percent",
                    fillcolor=SEG_COLORS[i % len(SEG_COLORS)],
                    hovertemplate="%{x}<br>" + str(seg) + ": %{y:.1f}%<extra></extra>"))
            mix.update_layout(margin={"t": 10, "r": 10, "b": 50, "l": 50}, height=240,
                              paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)",
                              xaxis={"tickangle": -45, "tickfont": {"size": 8},
                                     "dtick": max(1, len(q_list) // 16),
                                     "title": {"text": "Quarter",
                                               "font": {"size": 10}}},
                              yaxis={"title": "% of portfolio", "gridcolor": "#f1f5f9",
                                     "tickfont": {"size": 9}, "range": [0, 100]},
                              legend={"orientation": "h", "y": -0.35,
                                      "font": {"size": 9}}, showlegend=True)
            segmix = dcc.Graph(figure=mix, config=GRAPH_CFG)

        # ── Retained Portfolio CRR section ──
        ret_snap = ret_snap or cq
        ret_idx = quarters.index(ret_snap) if ret_snap in quarters else -1
        ret_pq = quarters[ret_idx - 1] if ret_idx > 0 else ret_snap
        ret_data = get_q(metrics, ret_snap)
        crr = (ret_data.get("population") or {}).get("crr_analysis") or {}
        mig = crr.get("crr_migration_matrix") or {"grades": [], "matrix": {}}

        chart_title = ("Customer Risk Rating Change — Retained Facilities"
                       if crr_view == "change" else
                       "Existing Customer Exposure Change ($M per CRR Grade)")
        by_crr = crr.get("by_crr") or []
        if not by_crr:
            crr_chart = empty_note("No retained-facility migration data available "
                                   "for this quarter pair.")
            crr_summary = empty_note("—")
        else:
            grades = [r.get("crr") for r in by_crr]
            x_common = {"type": "category", "categoryorder": "array",
                        "categoryarray": grades,
                        "title": {"text": "<b>CRR Grade</b>",
                                  "font": {"size": 12, "color": "#111827"}},
                        "tickfont": {"size": 11, "color": "#111827"},
                        "showgrid": False}
            if crr_view == "change":
                f = go.Figure([
                    go.Bar(name="↑ Upgrades", x=grades,
                           y=[r.get("upgrades") for r in by_crr],
                           marker={"color": "#2563eb",
                                   "line": {"color": "#1d4ed8", "width": 1}},
                           hovertemplate="<b>CRR %{x}</b><br>Upgrades: +%{y}<extra></extra>"),
                    go.Bar(name="↓ Downgrades", x=grades,
                           y=[r.get("downgrades") for r in by_crr],
                           marker={"color": "#dc2626",
                                   "line": {"color": "#991b1b", "width": 1}},
                           hovertemplate="<b>CRR %{x}</b><br>Downgrades: %{y}<extra></extra>"),
                    go.Scatter(name="Net change", x=grades,
                               y=[r.get("net") for r in by_crr],
                               mode="lines+markers",
                               line={"color": "#0f1d35", "width": 2.5},
                               marker={"size": 7, "color": "#0f1d35",
                                       "line": {"color": "#fff", "width": 1.5}},
                               hovertemplate="<b>CRR %{x}</b><br>Net: %{y}<extra></extra>"),
                ])
                f.update_layout(barmode="relative", bargap=0.25,
                                margin={"t": 40, "r": 20, "b": 60, "l": 60}, height=320,
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)", xaxis=x_common,
                                yaxis={"title": "<b>Facilities (±)</b>",
                                       "gridcolor": "#e5e7eb",
                                       "zerolinecolor": "#0f1d35", "zerolinewidth": 2},
                                legend={"orientation": "h", "y": 1.12, "x": 0.5,
                                        "xanchor": "center", "font": {"size": 11}})
            else:
                vals = [r.get("balance_change") or 0 for r in by_crr]
                f = go.Figure(go.Bar(
                    x=grades, y=vals,
                    marker={"color": ["#16a34a" if v >= 0 else "#dc2626" for v in vals]},
                    text=[("+" if v >= 0 else "") + fmt(v, 1) for v in vals],
                    textposition="outside", textfont={"size": 10}, cliponaxis=False,
                    hovertemplate="<b>CRR %{x}</b><br>Δ Balance: $%{y:.1f}M<extra></extra>"))
                f.update_layout(bargap=0.25, margin={"t": 30, "r": 20, "b": 60, "l": 70},
                                height=320, paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)", xaxis=x_common,
                                yaxis={"title": "<b>Δ Balance ($M)</b>",
                                       "gridcolor": "#e5e7eb",
                                       "zerolinecolor": "#0f1d35", "zerolinewidth": 2},
                                showlegend=False)
            crr_chart = dcc.Graph(figure=f, config=GRAPH_CFG)

            s = crr.get("retained_summary") or {}
            m = crr.get("retained_metrics") or {}

            def fmt_m(v):
                return "—" if v is None else ("+" if v >= 0 else "") + fmt(v, 1) + "M"

            crr_summary = html.Div([
                simple_table(
                    ["Upgrade / Downgrade", "Count", "Funded Δ Balance"],
                    [html.Tr([td("Upgrades"),
                              td(fmt_n(s.get("upgrades_count")), color="#16a34a",
                                 fontWeight="600", textAlign="right"),
                              td(fmt_m(s.get("upgrades_balance")), color="#16a34a",
                                 textAlign="right")]),
                     html.Tr([td("Downgrades"),
                              td(fmt_n(s.get("downgrades_count")), color="#dc2626",
                                 fontWeight="600", textAlign="right"),
                              td(fmt_m(s.get("downgrades_balance")), color="#dc2626",
                                 textAlign="right")]),
                     html.Tr([td("Net", fontWeight="700"),
                              td(("+" if (s.get("net_count") or 0) >= 0 else "")
                                 + fmt_n(s.get("net_count")), fontWeight="700",
                                 textAlign="right",
                                 color="#16a34a" if (s.get("net_count") or 0) >= 0
                                 else "#dc2626"),
                              td(fmt_m(s.get("net_balance")), fontWeight="700",
                                 textAlign="right",
                                 color="#16a34a" if (s.get("net_balance") or 0) >= 0
                                 else "#dc2626")],
                             style={"background": "#f8fafc"})]),
                html.Div(style={"height": "12px"}),
                simple_table(
                    ["Retained Customers", "Avg CRR", "Imp PD"],
                    [html.Tr([td(q_label(ret_pq)),
                              td(fmt(m.get("prior_avg_crr"), 2), textAlign="right"),
                              td(pct(m.get("prior_imp_pd"), 2), textAlign="right")]),
                     html.Tr([td(q_label(ret_snap)),
                              td(fmt(m.get("current_avg_crr"), 2), textAlign="right"),
                              td(pct(m.get("current_imp_pd"), 2), textAlign="right")])]),
                html.Div(f"Based on {fmt_n(crr.get('retained_count'))} retained "
                         "facilities (FCL-ID present in both quarters).",
                         style={"marginTop": "10px", "fontSize": "10px",
                                "color": "#64748b", "fontStyle": "italic"}),
            ])

        matrix_title = (f"CRR Migration Matrix — {q_label(ret_snap)} "
                        "(no prior quarter available)"
                        if ret_pq == ret_snap else
                        f"CRR Migration Matrix — {q_label(ret_pq)} → {q_label(ret_snap)}")
        sel_stats = _crr_selection_stats(mig, crr_sel)
        matrix_el = _crr_matrix_component(mig, crr_sel)
        sample_el = _sample_section(metrics, crr_sel)

        # ── By segment table ──
        if slice_effective:
            seg_table = filtered_notice
        else:
            seg_rows = []
            for s in (full_pop.get("by_segment") or []):
                nc = s.get("net_change") or 0
                ncp = s.get("net_change_pct") or 0
                seg_rows.append(html.Tr([
                    td(s.get("segment")), td(fmt_n(s.get("prior_accounts"))),
                    td(pct(s.get("new_pct"))), td(pct(s.get("dropped_pct"))),
                    td(fmt_n(s.get("current_accounts"))),
                    td(f"{'+' if nc >= 0 else ''}{fmt_n(nc)}",
                       color="#16a34a" if nc >= 0 else "#dc2626"),
                    td(f"{'+' if ncp >= 0 else ''}{pct(ncp)}",
                       color="#16a34a" if ncp >= 0 else "#dc2626"),
                ]))
            seg_table = simple_table(
                ["Segment", "Prior Q Accounts", "New %", "Dropped %",
                 "Current Accounts", "Net Change #", "Net Change %"], seg_rows)

        title_q = "Port 2024 vs Port 2025" if cross else q_label(snapshot)
        return (kpis, movement, churn, segmix, chart_title, crr_chart,
                crr_summary, matrix_title, sel_stats, matrix_el, sample_el,
                seg_table, lens_text, title_q, chip, summary, snap_wrap_style)
