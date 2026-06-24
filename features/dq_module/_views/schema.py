"""Schema tab — port of pages/schema_page.py.

Cross-portfolio comparison only (the schema is fixed within a portfolio):
KPIs, P24↔P25 column diff, per-portfolio schema-vs-data reconciliation,
key-variable roster, data-types distribution, naming hygiene. No callbacks —
the whole tab is computed once from schema_diff + by_quarter[CQ].schema.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dash_table, dcc, html

from .common import (
    GRAPH_CFG, GRID2, P24_COLOR, P25_COLOR, SECTION, SECTION_IN_GRID,
    SECTION_TITLE, fmt, fmt_n, get_q, kpi_card, kpi_grid, pct, simple_table, td,
)

TAB = "schema"

# Above this row count, a flat list/table is replaced with a paginated,
# sortable, client-side-filterable DataTable so the page survives the real SQL
# source (40+ type changes, dozens of added/removed columns) instead of only
# the all-clean Excel test data.
_VOLUME_THRESHOLD = 8
_DT_PAGE = 10


def _tag_list(items, color):
    """Scrollable, bounded chip box for a list of column names.

    Caps its own height (never pushes the page) and announces overflow with a
    count, so 4 columns and 40 columns both render sanely.
    """
    if not items:
        return html.Span("None", style={"color": "#94a3b8", "fontSize": "11px"})
    chips = [html.Span(c, style={
        "display": "inline-block", "background": f"{color}18", "color": color,
        "border": f"1px solid {color}44", "borderRadius": "4px",
        "padding": "1px 6px", "fontFamily": "monospace", "fontSize": "10px",
        "margin": "2px"}) for c in items]
    box = html.Div(chips, style={
        "maxHeight": "132px", "overflowY": "auto", "padding": "4px",
        "border": "1px solid #f1f5f9", "borderRadius": "6px",
        "background": "#fafafa"})
    if len(items) <= 12:
        return box
    return html.Div([
        html.Div(f"{len(items)} columns · scroll for the full list",
                 style={"fontSize": "10px", "color": "#94a3b8",
                        "margin": "0 0 3px 2px"}),
        box])


def _drift_table(columns, rows, page=_DT_PAGE):
    """Volume-safe table: native pagination + sort + filter, zero callbacks.

    `columns` is a list of (header, id) pairs; `rows` a list of dicts keyed by
    those ids. Below the volume threshold it still paginates harmlessly.
    """
    return dash_table.DataTable(
        columns=[{"name": h, "id": i} for h, i in columns],
        data=rows,
        page_size=page,
        page_action="native",
        sort_action="native",
        filter_action="native" if len(rows) > _VOLUME_THRESHOLD else "none",
        style_table={"overflowX": "auto", "border": "1px solid #e2e8f0",
                     "borderRadius": "6px"},
        style_header={"backgroundColor": "#0f1d35", "color": "#fff",
                      "fontWeight": "700", "fontSize": "10px",
                      "whiteSpace": "nowrap", "border": "1px solid #1e293b",
                      "textAlign": "left"},
        style_cell={"fontSize": "11px", "padding": "5px 10px",
                    "fontFamily": "monospace", "border": "1px solid #f1f5f9",
                    "textAlign": "left", "whiteSpace": "nowrap",
                    "maxWidth": "320px", "overflow": "hidden",
                    "textOverflow": "ellipsis", "color": "#0f172a"},
        style_filter={"backgroundColor": "#f8fafc"},
        style_data_conditional=[{"if": {"row_index": "odd"},
                                 "backgroundColor": "#fafafa"}],
    )


def _ok_badge(ok: bool):
    return html.Span("✓" if ok else "✖", style={
        "display": "inline-block", "width": "18px", "height": "18px",
        "borderRadius": "50%", "textAlign": "center", "lineHeight": "18px",
        "fontSize": "11px", "fontWeight": "700",
        "background": "#dcfce7" if ok else "#fee2e2",
        "color": "#15803d" if ok else "#991b1b"})


def _portfolio_card(label, vs, color):
    missing = vs.get("missing_from_data") or []
    extra = vs.get("extra_in_data") or []
    type_issues = vs.get("type_issues") or []

    def block(title, title_color, items, ok_text, table=None):
        head = html.Div(f"{title} ({len(items)})", style={
            "fontSize": "10px", "fontWeight": "700", "color": title_color,
            "textTransform": "uppercase", "letterSpacing": ".05em",
            "marginBottom": "3px"})
        if not items:
            return html.Div([head, html.Div(ok_text, style={
                "fontSize": "11px", "color": "#16a34a"})],
                style={"marginBottom": "8px"})
        # NB: `table if table is not None` — a childless Dash component is
        # falsy (len 0), so `table or …` would silently drop the DataTable.
        body = table if table is not None else _tag_list(items, title_color)
        return html.Div([head, body], style={"marginBottom": "8px"})

    type_table = None
    if type_issues:
        type_table = _drift_table(
            [("Column", "column"), ("Expected", "expected"), ("Actual", "actual")],
            [{"column": r.get("column"), "expected": r.get("expected"),
              "actual": r.get("actual")} for r in type_issues],
            page=6)

    return html.Div([
        html.Div([
            html.Span(style={"display": "inline-block", "width": "8px", "height": "8px",
                             "borderRadius": "50%", "background": color,
                             "marginRight": "8px"}),
            html.Strong(label, style={"fontSize": "13px", "color": "#111827"}),
            html.Span(f"{fmt_n(vs.get('data_cols'))} cols • "
                      f"{fmt(vs.get('coverage_pct') or 0, 1)}% schema coverage",
                      style={"marginLeft": "auto", "fontSize": "11px", "color": "#64748b"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),
        block("Declared in schema, missing from data", "#dc2626", missing,
              "✅ all declared cols present"),
        block("In data but not declared in schema", "#d97706", extra,
              "✅ all data cols are declared"),
        block("Type mismatch vs schema", "#ea580c", type_issues,
              "✅ all types match the schema", table=type_table),
    ], style={"border": "1px solid #e2e8f0", "borderRadius": "8px",
              "padding": "12px", "background": "#fff"})


def layout(metrics: dict):
    cq = metrics["latest_quarter"]
    s = get_q(metrics, cq).get("schema") or {}
    sd = metrics.get("schema_diff") or {}
    v24 = sd.get("port24_vs_schema") or {}
    v25 = sd.get("port25_vs_schema") or {}
    roster = sd.get("key_var_roster") or []
    hygiene = sd.get("naming_hygiene") or []
    added = sd.get("added") or []
    removed = sd.get("removed") or []
    type_changes = sd.get("type_changes") or []
    net = sd.get("net_change") or 0
    type_dist = s.get("types_distribution") or []

    # Drift KPIs go loud when non-zero: green when clean, red/amber when the
    # schema contract actually moved (the state the real SQL source will hit).
    drift_color = lambda n: "#dc2626" if n else "#16a34a"
    drift_accent = lambda n, c: c if n else None

    kpis = kpi_grid([
        kpi_card("Schema columns",
                 fmt_n(v25.get("schema_cols") or v24.get("schema_cols") or 0),
                 "from schema file"),
        kpi_card("Original port cols", fmt_n(sd.get("port24_columns")),
                 f"coverage {fmt(v24.get('coverage_pct') or 0, 1)}%"),
        kpi_card("New port cols", fmt_n(sd.get("port25_columns")),
                 f"coverage {fmt(v25.get('coverage_pct') or 0, 1)}%"),
        kpi_card("Added cols", fmt_n(len(added)), "present in new port only",
                 color=drift_color(len(added)), accent=drift_accent(len(added), "#16a34a")),
        kpi_card("Removed cols", fmt_n(len(removed)), "present in original port only",
                 color=drift_color(len(removed)), accent=drift_accent(len(removed), "#dc2626")),
        kpi_card("Data type change", fmt_n(len(type_changes)),
                 "dtype mismatch across files",
                 color=drift_color(len(type_changes)),
                 accent=drift_accent(len(type_changes), "#d97706")),
    ], 6)

    def stat_box(value, label, color, bg):
        return html.Div([
            html.Div(value, style={"fontSize": "18px", "fontWeight": "700", "color": color}),
            html.Div(label, style={"fontSize": "10px", "color": "#64748b"}),
        ], style={"textAlign": "center", "padding": "8px", "background": bg,
                  "borderRadius": "6px"})

    diff_stats = html.Div([
        stat_box(sd.get("port25_columns") or "—", "Port 2025 columns", "#16a34a", "#f0fdf4"),
        stat_box(sd.get("port24_columns") or "—", "Port 2024 columns", "#2563eb", "#f0f9ff"),
        stat_box(f"{'+' if net > 0 else ''}{net}", "Net column change",
                 "#16a34a" if net > 0 else "#dc2626" if net < 0 else "#64748b", "#f8fafc"),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
              "gap": "8px", "marginBottom": "12px"})

    tc_block = (_drift_table(
        [("Column", "column"), ("Port 2024", "port24_type"),
         ("Port 2025", "port25_type")],
        [{"column": t.get("column"), "port24_type": t.get("port24_type"),
          "port25_type": t.get("port25_type")} for t in type_changes])
        if type_changes else
        html.Span("No type changes detected", style={"color": "#94a3b8", "fontSize": "11px"}))

    diff_card = html.Div([
        html.Div("Port 2024 vs Port 2025 — Column Diff", style=SECTION_TITLE),
        diff_stats,
        html.Div([html.Div(f"✚ Added in Port 2025 ({len(added)})",
                           style={"fontSize": "11px", "fontWeight": "700",
                                  "color": "#16a34a", "marginBottom": "4px"}),
                  _tag_list(added, "#16a34a")], style={"marginBottom": "8px"}),
        html.Div([html.Div(f"✖ Removed from Port 2024 ({len(removed)})",
                           style={"fontSize": "11px", "fontWeight": "700",
                                  "color": "#dc2626", "marginBottom": "4px"}),
                  _tag_list(removed, "#dc2626")], style={"marginBottom": "8px"}),
        html.Div([html.Div(f"⚠ Type Changes ({len(type_changes)})",
                           style={"fontSize": "11px", "fontWeight": "700",
                                  "color": "#d97706", "marginBottom": "4px"}),
                  tc_block]),
    ], style=SECTION)

    recon_card = html.Div([
        html.Div("Schema-vs-Data Reconciliation — Each Portfolio", style=SECTION_TITLE),
        html.Div("Compares each portfolio file against the declared schema. Surfaces gaps "
                 "(cols defined in schema but absent from data), extras (cols in data but "
                 "not declared), and type mismatches.",
                 style={"fontSize": "11px", "color": "#64748b", "marginBottom": "12px"}),
        html.Div([_portfolio_card("Port 2024", v24, P24_COLOR),
                  _portfolio_card("Port 2025", v25, P25_COLOR)],
                 style={"display": "grid", "gridTemplateColumns": "repeat(2, 1fr)",
                        "gap": "12px"}),
    ], style=SECTION)

    # Surface any key-variable gaps at the top of the roster — in a long real
    # roster a single missing key var would otherwise hide mid-table.
    roster = sorted(roster, key=lambda r: bool(r.get("in_p24") and r.get("in_p25")))
    roster_rows = []
    n_key_issues = 0
    for r in roster:
        both = r.get("in_p24") and r.get("in_p25")
        if not both:
            n_key_issues += 1
        status = ("In both" if both else
                  "P25 only" if r.get("in_p25") else
                  "P24 only" if r.get("in_p24") else "Missing")
        # A key variable absent from either portfolio is high-severity drift —
        # tint the whole row so it can't be skimmed past in a long roster.
        row_style = None if both else {"background": "#fef2f2"}
        roster_rows.append(html.Tr([
            td(r.get("column"), fontFamily="monospace"),
            td(_ok_badge(bool(r.get("in_p24"))), textAlign="center"),
            td(_ok_badge(bool(r.get("in_p25"))), textAlign="center"),
            td(html.Span(status, style={"fontSize": "11px", "fontWeight": "600",
                                        "color": "#16a34a" if both else "#dc2626"})),
            td(r.get("data_type"), fontSize="10px", color="#64748b"),
            td(r.get("usage"), fontSize="10px", color="#64748b"),
        ], style=row_style))
    key_issue_note = (
        html.Span(f"⚠ {n_key_issues} key variable(s) missing from a portfolio",
                  style={"marginLeft": "auto", "fontSize": "11px",
                         "fontWeight": "700", "color": "#b91c1c",
                         "background": "#fef2f2", "border": "1px solid #fecaca",
                         "borderRadius": "5px", "padding": "2px 8px"})
        if n_key_issues else
        html.Span("✓ all present in both portfolios",
                  style={"marginLeft": "auto", "fontSize": "11px",
                         "fontWeight": "600", "color": "#15803d"}))
    roster_card = html.Div([
        html.Div([html.Div("🔑 Key Variables Roster", style=dict(SECTION_TITLE, margin=0)),
                  key_issue_note],
                 style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}),
        html.Div(["Columns flagged ", html.Code("key_variable=Y"),
                  " in the schema. Must be present in both portfolios."],
                 style={"fontSize": "11px", "color": "#64748b", "marginBottom": "8px"}),
        (simple_table(["Column", "In P24", "In P25", "Status", "Data Type", "Usage"],
                      roster_rows, font_size="12px")
         if roster else html.Div("No key variables flagged in the schema.",
                                 style={"color": "#94a3b8", "fontSize": "12px",
                                        "padding": "8px"})),
    ], style=SECTION)

    pie = go.Figure()
    if type_dist:
        pie.add_trace(go.Pie(
            values=[t.get("count") for t in type_dist],
            labels=[t.get("type") for t in type_dist], hole=0.6,
            marker={"colors": ["#2563eb", "#16a34a", "#d97706", "#7c3aed", "#6b7280"]},
            textinfo="percent", textfont={"size": 10}))
    pie.update_layout(margin={"t": 10, "r": 10, "b": 10, "l": 10}, height=220,
                      paper_bgcolor="rgba(0,0,0,0)", legend={"font": {"size": 10}})

    types_card = html.Div([
        html.Div([
            html.Div("Data Types Distribution — Port 2025", style=SECTION_TITLE),
            dcc.Graph(id=f"dqd-{TAB}-chart-types", figure=pie, config=GRAPH_CFG),
        ], style=SECTION_IN_GRID),
        html.Div([
            html.Div("Data Types Summary", style=SECTION_TITLE),
            simple_table(["Type", "Columns", "%"],
                         [html.Tr([td(t.get("type")), td(fmt_n(t.get("count"))),
                                   td(pct(t.get("pct")))]) for t in type_dist]),
            html.Div([
                html.Div(f"📋 Schema declares {fmt_n(s.get('expected_columns'))} columns total"),
                html.Div(f"🔑 {fmt_n(len(roster))} flagged as key variables"),
                html.Div("📊 Single fact table (no joins / dimensions)"),
            ], style={"marginTop": "12px", "fontSize": "11px", "color": "#64748b"}),
        ], style=SECTION_IN_GRID),
    ], style=GRID2)

    children = [
        html.Div([
            html.H2("Data Schema Dashboard", style={"margin": "0 0 6px", "fontSize": "20px"}),
            html.P(["The portfolio is a single table whose structure is fixed by the schema "
                    "file. The interesting comparison is ",
                    html.Strong("Port 2024 vs Port 2025"),
                    " against each other and against the schema definition — quarter or "
                    "year selectors do not apply here."],
                   style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
        ], style=SECTION),
        kpis, diff_card, recon_card, roster_card, types_card,
    ]

    if hygiene:
        children.append(html.Div([
            html.Div(f"⚠️ Naming Hygiene Findings ({len(hygiene)})", style=SECTION_TITLE),
            html.Div("Potential naming issues that can cause silent data joins to fail "
                     "or duplicate columns.",
                     style={"fontSize": "11px", "color": "#64748b", "marginBottom": "8px"}),
            _drift_table(
                [("Column(s)", "column"), ("Issue", "issue")],
                [{"column": h.get("column"), "issue": h.get("issue")} for h in hygiene],
                page=8),
        ], style=SECTION))

    return children


def register_callbacks(app, metrics: dict):
    # Static tab — everything is computed at layout time.
    return None
