"""Completeness tab — port of pages/completeness_page.py (the largest page).

Two explicit questions (drift-style), replacing the generic comparison mode:
  Q1 · Within-Portfolio Shift   — how did missingness shift between two
       Port 2025 snapshots? Free quarter-pair selector (any pair).
  Q2 · Cross-Portfolio Benchmark — is Port 2025 cleaner than Port 2024?
       Fixed year-end pair (P24 2024Q4 → P25 2025Q4).

Column filters (scope / severity / type / usage) are global across both
questions. In Q2 the Port 2024 per-column rows are thin (missing % + severity
only), so type/usage filters are evaluated on the Port 2025 snapshot per
column name and applied to both sides.

The Missing Values Migration Matrix is clickable: each click toggles a
(prior→current) bucket cell in a dcc.Store; when the selection is non-empty
every filtered view narrows to the matching variables. The matrix itself
always shows the full filtered universe (it IS the selector). Switching
questions clears the selection.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from .common import (
    GRAPH_CFG, GRID2, GRID3, MISSING_BUCKETS, MISSING_BUCKET_COLORS,
    MISSING_BUCKET_NOTE, MISSING_BUCKET_RANGES, MISSING_BUCKET_TONES, MUTED,
    P24_COLOR, P25_COLOR, SECTION, SECTION_IN_GRID, SECTION_TITLE,
    dtype_bucket, empty_note, fig, fmt, fmt_n, get_q, help_tip, kpi_card,
    kpi_grid, line_trace, missing_bucket, pct, q_label, question_bar,
    question_chip, quarter_pair_picker, simple_table, spark, td,
)

# ── Hover-help copy (plain-English metric explanations) ───────────────────
SEG_COMPLETENESS_HELP = (
    "Completeness % = share of populated (non-missing) cells across the "
    "schema-flagged key variables, for the accounts in each segment. "
    "Computed as 1 − (missing cells ÷ total cells), where total cells = "
    "accounts in the segment × number of key variables. Latest snapshot only; "
    "Δ compares the same segment against the prior quarter."
)
SEVERITY_HELP = (
    "Each column is placed in one missing-data severity bucket by its missing "
    "%: No Missings = 0% · Low = ≤1% · Medium = >1% to ≤10% · High = >10%. The "
    "four cards count how many columns fall in each bucket within the current "
    "scope/type/usage filter. Δ is the change in that count vs the baseline "
    "snapshot."
)

TAB = "completeness"

Q_META = {
    "q1": {
        "label": "Within-Portfolio Shift",
        "color": "#2563eb",
        "desc": "How did missingness shift between two Port 2025 snapshots?",
        "detail": ("Pick any prior → current snapshot pair below. The migration "
                   "matrix, bucket deltas, Δ columns, and the trend window all "
                   "compare those two Port 2025 snapshots."),
    },
    "q2": {
        "label": "Cross-Portfolio Benchmark",
        "color": "#7c3aed",
        "desc": "Is Port 2025 cleaner than Port 2024?",
        "detail": ("Fixed year-end pair: Port 2024's last snapshot vs Port 2025's "
                   "last snapshot. Port 2024 column metadata is limited to "
                   "missing % and severity, so type/usage filters are evaluated "
                   "on the Port 2025 snapshot."),
    },
}


# ── Severity (canonical: derived from missing_pct via missing_bucket) ──────

def _sev_badge(bucket):
    return html.Span(bucket, style={
        "display": "inline-block", "padding": "1px 8px", "borderRadius": "10px",
        "fontSize": "10px", "fontWeight": "700",
        "background": MISSING_BUCKET_COLORS.get(bucket, "#f1f5f9"),
        "color": MISSING_BUCKET_TONES.get(bucket, "#475569")})


# ── Filters ───────────────────────────────────────────────────────────────

def _passes_filter(r, scope, sev, dtype, usage, mig_var_set):
    if mig_var_set is not None and r.get("column") not in mig_var_set:
        return False
    if scope == "key" and not r.get("is_key_var"):
        return False
    if scope == "non_key" and r.get("is_key_var"):
        return False
    if sev != "all" and missing_bucket(r.get("missing_pct")) != sev:
        return False
    if dtype != "all" and dtype_bucket(r) != dtype:
        return False
    if usage != "all" and (r.get("usage") or "—") != usage:
        return False
    return True


# ── Snapshot-pair resolution (per question) ───────────────────────────────

def _snapshot_by_column(metrics, quarter, portfolio):
    if not quarter:
        return []
    if portfolio == "port24":
        ts = (metrics.get("port24") or {}).get("time_series") or {}
        return (ts.get("completeness_by_column") or {}).get(quarter) or []
    return (get_q(metrics, quarter).get("completeness") or {}).get("by_column") or []


def _year_end_quarter(year, quarters):
    cands = [q for q in (quarters or []) if str(q)[:4] == str(year)]
    return cands[-1] if cands else None


def _p24_overall(metrics, quarter):
    """Record-weighted Port 2024 overall completeness % at a quarter."""
    rows = ((metrics.get("port24") or {}).get("time_series") or {}) \
        .get("completeness_over_time") or []
    for r in rows:
        if str(r.get("quarter")) == str(quarter):
            return r.get("value")
    return None


def _resolve_pair(metrics, question, prior_q, current_q):
    """The active question's snapshot pair, incl. record-weighted overall %
    for both endpoints (the same basis as the headline KPI — fix for the old
    column-average baseline)."""
    quarters = metrics.get("quarters") or []
    if question == "q2":
        q24 = (metrics.get("port24") or {}).get("quarters") or []
        yr24 = max((int(str(q)[:4]) for q in q24), default=None)
        yr25 = max((int(str(q)[:4]) for q in quarters), default=None)
        prior_q = _year_end_quarter(yr24, q24)
        current_q = _year_end_quarter(yr25, quarters)
        return {
            "question": "q2",
            "prior_q": prior_q, "current_q": current_q,
            "prior": _snapshot_by_column(metrics, prior_q, "port24"),
            "current": _snapshot_by_column(metrics, current_q, "port25"),
            "prior_overall": _p24_overall(metrics, prior_q),
            "label": (f"Port 2024 {q_label(prior_q)} → Port 2025 "
                      f"{q_label(current_q)} (cross-portfolio, year-end "
                      "snapshots)"),
            "prior_label": q_label(prior_q) or "—",
            "current_label": q_label(current_q) or "—",
            "invalid": None,
        }
    prior_q = prior_q or metrics.get("prior_quarter")
    current_q = current_q or metrics.get("latest_quarter")
    invalid = None
    if prior_q and current_q:
        if prior_q == current_q:
            invalid = "Pick two distinct snapshots."
        elif str(prior_q) > str(current_q):
            invalid = "The prior snapshot should precede the current one."
    prior_comp = (get_q(metrics, prior_q).get("completeness") or {})
    return {
        "question": "q1",
        "prior_q": prior_q, "current_q": current_q,
        "prior": _snapshot_by_column(metrics, prior_q, "port25"),
        "current": _snapshot_by_column(metrics, current_q, "port25"),
        "prior_overall": prior_comp.get("overall_pct"),
        "label": (f"Port 2025 {q_label(prior_q)} → Port 2025 "
                  f"{q_label(current_q)} (same portfolio, snapshot pair)"),
        "prior_label": q_label(prior_q) or "—",
        "current_label": q_label(current_q) or "—",
        "invalid": invalid,
    }


def _compute_mig_var_set(selection, pair):
    """Set of columns whose (prior→current) bucket transition is selected."""
    if not selection:
        return None
    sel = set(selection)
    prior_map = {r["column"]: r for r in (pair.get("prior") or [])}
    cur_map = {r["column"]: r for r in (pair.get("current") or [])}
    out = set()
    for col in set(prior_map) | set(cur_map):
        p, c = prior_map.get(col), cur_map.get(col)
        if not p or not c:
            continue
        key = missing_bucket(p.get("missing_pct")) + "|" + missing_bucket(c.get("missing_pct"))
        if key in sel:
            out.add(col)
    return out


def _build_migration_matrix(prior_rows, current_rows):
    prior_map = {r["column"]: r for r in prior_rows}
    cur_map = {r["column"]: r for r in current_rows}
    matrix = {s1: {s2: [] for s2 in MISSING_BUCKETS} for s1 in MISSING_BUCKETS}
    added, removed = [], []
    improved = stable = worsened = 0
    for col in set(prior_map) | set(cur_map):
        p, c = prior_map.get(col), cur_map.get(col)
        if not p and c:
            added.append(c)
            continue
        if p and not c:
            removed.append(p)
            continue
        psev = missing_bucket(p.get("missing_pct"))
        csev = missing_bucket(c.get("missing_pct"))
        matrix[psev][csev].append(col)
        pi, ci = MISSING_BUCKETS.index(psev), MISSING_BUCKETS.index(csev)
        if ci < pi:
            improved += 1
        elif ci > pi:
            worsened += 1
        else:
            stable += 1
    return {"matrix": matrix, "added": added, "removed": removed,
            "improved": improved, "stable": stable, "worsened": worsened}


def _matrix_component(M, pair, selection, extra_note=None):
    sel = set(selection or [])

    def cell(i, j):
        s1, s2 = MISSING_BUCKETS[i], MISSING_BUCKETS[j]
        cols = M["matrix"][s1][s2]
        n = len(cols)
        if n == 0:
            bg, fg = "#fafafa", "#cbd5e1"
        elif i == j:
            bg, fg = "#e2e8f0", "#475569"
        elif j < i:
            bg, fg = "#bbf7d0", "#166534"
        else:
            bg, fg = "#fecaca", "#991b1b"
        key = f"{s1}|{s2}"
        selected = key in sel
        style = {"width": "100%", "minWidth": "64px", "padding": "10px 4px",
                 "textAlign": "center", "fontWeight": "700", "fontSize": "14px",
                 "background": bg, "color": fg, "cursor": "pointer" if n else "default",
                 "border": "3px solid #9a3412" if selected else "1px solid #e2e8f0"}
        title = (f"{s1} → {s2} · {n} variable(s): " + ", ".join(cols[:5])
                 + (f" (+{n - 5} more)" if n > 5 else "")) if n else ""
        content = [str(n) if n else ""]
        if selected:
            content.append(html.Div("SELECTED", style={"fontSize": "8px",
                                                       "color": "#9a3412",
                                                       "fontWeight": "700"}))
        if n:
            return html.Td(html.Button(content, title=title,
                                       id={"type": "dqd-comp-mig", "index": key},
                                       n_clicks=0, style=style),
                           style={"padding": 0})
        return html.Td(content, title=title, style=dict(style, cursor="default"))

    hdr_style = {"padding": "6px 10px", "fontSize": "10px", "fontWeight": "700",
                 "color": "#64748b", "textTransform": "uppercase",
                 "letterSpacing": ".05em", "textAlign": "center",
                 "border": "1px solid #e2e8f0"}
    header = html.Tr([html.Td("", style={"background": "#f8fafc", "width": "96px",
                                         "border": "1px solid #e2e8f0"})] +
                     [html.Th(s, style=dict(hdr_style, width="80px",
                                            background=MISSING_BUCKET_COLORS[s]))
                      for s in MISSING_BUCKETS])
    body = []
    for i, s1 in enumerate(MISSING_BUCKETS):
        body.append(html.Tr(
            [html.Td(s1, style=dict(hdr_style, textAlign="right",
                                    background=MISSING_BUCKET_COLORS[s1]))] +
            [cell(i, j) for j in range(len(MISSING_BUCKETS))]))

    note_bits = ["Click a cell to toggle it in the drilldown selection "
                 "(multi-select); every other chart filters to the matching "
                 "variables. The matrix itself always shows all filtered columns "
                 "— your cell selection narrows the other sections, not this grid."]
    if M["added"] or M["removed"]:
        note_bits.append(f" Schema diff: +{len(M['added'])} added, "
                         f"−{len(M['removed'])} removed between snapshots.")
    if extra_note:
        note_bits.append(f" {extra_note}")

    return html.Div([
        html.Div(f"↓ Prior ({pair['prior_label']})   →   Current ({pair['current_label']}) →",
                 style={"fontSize": "10px", "color": "#64748b", "fontWeight": "700",
                        "textTransform": "uppercase", "marginBottom": "6px"}),
        html.Table([html.Thead(header), html.Tbody(body)],
                   style={"borderCollapse": "collapse", "fontSize": "11px",
                          "tableLayout": "fixed", "width": "416px"}),
        html.Div(note_bits, style={"marginTop": "10px", "fontSize": "10px",
                                   "color": "#64748b"}),
    ])


def _matrix_summary(M):
    total = M["improved"] + M["stable"] + M["worsened"] or 1

    def box(label, n, fg, bg):
        return html.Div([
            html.Div(label, style={"fontSize": "11px", "color": fg, "fontWeight": "700"}),
            html.Div(str(n), style={"fontSize": "22px", "fontWeight": "800", "color": fg}),
            html.Div(f"{round(n / total * 100)}%", style={"fontSize": "9px", "color": fg}),
        ], style={"textAlign": "center", "padding": "10px", "background": bg,
                  "borderRadius": "6px"})

    legend_rows = [html.Tr([
        td(s, fontWeight="700", background=MISSING_BUCKET_COLORS[s]),
        td(MISSING_BUCKET_RANGES[s], fontFamily="monospace", color="#64748b"),
    ]) for s in MISSING_BUCKETS]

    return html.Div([
        html.Div([box("Improved", M["improved"], "#15803d", "#dcfce7"),
                  box("Stable", M["stable"], "#475569", "#e2e8f0"),
                  box("Worsened", M["worsened"], "#991b1b", "#fecaca")],
                 style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)",
                        "gap": "8px", "marginBottom": "14px"}),
        html.Div("Bucket Definitions", style={"fontSize": "11px", "fontWeight": "700",
                                              "color": "#64748b",
                                              "textTransform": "uppercase",
                                              "letterSpacing": ".05em",
                                              "marginBottom": "6px"}),
        simple_table(["Bucket", "Missing % range"], legend_rows),
    ])


# ── Filtered time series (port of _filteredCompTS) ────────────────────────

def _filtered_comp_ts(metrics, portfolio, filt):
    out = []
    if portfolio == "port24":
        by_q = ((metrics.get("port24") or {}).get("time_series") or {}) \
            .get("completeness_by_column") or {}
        for q in sorted(by_q):
            cols = [c for c in (by_q[q] or []) if filt(c)]
            value = (100 - sum(float(c.get("missing_pct") or 0) for c in cols) / len(cols)
                     if cols else None)
            out.append({"quarter": q, "label": q_label(q), "value": value})
    else:
        for q in metrics.get("quarters") or []:
            cols = [c for c in ((get_q(metrics, q).get("completeness") or {})
                                .get("by_column") or []) if filt(c)]
            value = (100 - sum(float(c.get("missing_pct") or 0) for c in cols) / len(cols)
                     if cols else None)
            out.append({"quarter": q, "label": q_label(q), "value": value})
    return out


def _pair_vlines(pair):
    """Dotted vertical guides marking the selected snapshot pair on a trend
    chart (category axis x = q_label). Empty for an invalid pair."""
    if pair.get("invalid"):
        return []
    shapes = []
    for q in (pair.get("prior_q"), pair.get("current_q")):
        lab = q_label(q)
        if lab:
            shapes.append({"type": "line", "x0": lab, "x1": lab,
                           "yref": "paper", "y0": 0, "y1": 1,
                           "line": {"color": "#94a3b8", "width": 1, "dash": "dot"}})
    return shapes


def _trend_window(metrics, pair, min_n: int = 12):
    """Quarters to plot for a Q1 trend: a trailing window of at least min_n
    ending at the current snapshot, extended back to include the prior one."""
    quarters = metrics.get("quarters") or []
    if not quarters:
        return set()
    cq, pq = pair.get("current_q"), pair.get("prior_q")
    ci = quarters.index(cq) if cq in quarters else len(quarters) - 1
    pi = quarters.index(pq) if pq in quarters else ci
    start = max(0, min(pi, ci - (min_n - 1)))
    return set(quarters[start:ci + 1])


def _thin_ticks(labels, max_n: int = 14):
    """Ordered-unique subset of category labels so the x-axis isn't crammed."""
    seen = list(dict.fromkeys(l for l in labels if l))
    if len(seen) <= max_n:
        return seen
    step = -(-len(seen) // max_n)  # ceil
    keep = seen[::step]
    if seen[-1] not in keep:
        keep.append(seen[-1])
    return keep


def _trend_fig(traces, all_labels, pair, y_range=None, y_mode=None):
    """Shared completeness trend layout: thinned x-ticks, no y-title (the
    section header already names the metric), and an explicit bottom margin
    sized to hold the rotated quarter labels + axis title inside the figure
    (the proven pattern used by the Pareto chart — automargin mis-sizes
    rotated category ticks and the labels spill into the section below)."""
    yaxis = {"gridcolor": "#f1f5f9", "tickfont": {"size": 9}}
    if y_range:
        yaxis["range"] = y_range
    if y_mode:
        yaxis["rangemode"] = y_mode
    layout = {
        "margin": {"t": 14, "r": 16, "b": 78, "l": 46}, "height": 250,
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "xaxis": {"type": "category", "tickangle": -45, "tickfont": {"size": 9},
                  "tickmode": "array", "tickvals": _thin_ticks(all_labels),
                  "showgrid": False,
                  "title": {"text": "Quarter", "font": {"size": 10},
                            "standoff": 6}},
        "yaxis": yaxis,
        "legend": {"orientation": "h", "y": 1.12, "x": 0, "font": {"size": 9}},
        "showlegend": True, "shapes": _pair_vlines(pair),
    }
    return fig(traces, layout)


# ── Additional segmentations (static, precomputed) ────────────────────────

def _extra_segments(metrics):
    segs = metrics.get("completeness_segments") or {}
    if not segs:
        return []

    cards = []
    for dim_key, entry in segs.items():
        rows = entry.get("rows") or []
        prior_label = (f"vs {q_label(entry.get('prior_q'))}"
                       if entry.get("prior_q") else "no prior snapshot")
        body = []
        for r in rows:
            comp_v = r.get("completeness_pct") or 0
            comp_color = ("#16a34a" if comp_v >= 99 else "#65a30d" if comp_v >= 95
                          else "#d97706" if comp_v >= 90 else "#dc2626")
            miss_v = r.get("missing_pct") or 0
            miss_color = "#64748b" if miss_v <= 1 else "#d97706" if miss_v <= 10 else "#dc2626"
            delta = r.get("comp_delta")
            if delta is None:
                delta_cell = html.Span("—", style={"color": "#94a3b8"})
            elif abs(delta) < 0.01:
                delta_cell = html.Span("0.00pp", style={"color": "#64748b"})
            else:
                c = "#16a34a" if delta > 0 else "#dc2626"
                sym = "▲" if delta > 0 else "▼"
                delta_cell = html.Span(f"{sym} {'+' if delta > 0 else ''}{fmt(delta, 2)}pp",
                                       style={"color": c, "fontWeight": "600"})
            body.append(html.Tr([
                td(r.get("segment"), fontWeight="600", color="#0f172a"),
                td(fmt_n(r.get("accounts") or 0), textAlign="right", fontFamily="monospace"),
                td(html.Span(pct(comp_v, 2), style={"color": comp_color,
                                                    "fontWeight": "600"}),
                   textAlign="right"),
                td(html.Span(pct(miss_v, 2), style={"color": miss_color}),
                   textAlign="right"),
                td(delta_cell, textAlign="right"),
            ]))
        cards.append(html.Div([
            html.Div([
                html.Div(entry.get("label") or dim_key,
                         style=dict(SECTION_TITLE, margin=0)),
                html.Div(f"{len(rows)} segment(s) · {prior_label}",
                         style={"fontSize": "10px", "color": "#64748b",
                                "fontFamily": "monospace"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "baseline", "marginBottom": "4px"}),
            html.Div(["Completeness across the schema-flagged key variables, grouped by ",
                      html.Code(entry.get("column") or ""),
                      ". Δ compares against the prior quarter's snapshot."],
                     style={"fontSize": "11px", "color": "#64748b", "marginBottom": "8px"}),
            simple_table(["Segment", "Accounts", "Completeness %", "Missing %",
                          "Δ vs prior"], body,
                         header_styles=[None, {"textAlign": "right"},
                                        {"textAlign": "right"}, {"textAlign": "right"},
                                        {"textAlign": "right"}]),
        ], style=SECTION_IN_GRID))

    return [
        html.Div(["Additional Segmentations ",
                  help_tip(SEG_COMPLETENESS_HELP),
                  html.Span(f" (key variables across {len(segs)} extra dimensions · "
                            f"latest snapshot — ignores the filters and selected "
                            f"question above)",
                            style={"fontSize": "10px", "fontWeight": "500",
                                   "color": "#94a3b8"})],
                 style={"fontSize": "12px", "fontWeight": "700", "color": "#0f172a",
                        "textTransform": "uppercase", "letterSpacing": ".05em",
                        "margin": "18px 0 8px", "paddingTop": "14px",
                        "borderTop": "1px solid #e2e8f0"}),
        html.Div(cards, style=GRID2),
    ]


# ── Layout ────────────────────────────────────────────────────────────────

def layout(metrics: dict):
    cq = metrics["latest_quarter"]
    comp = get_q(metrics, cq).get("completeness") or {}
    all_cols = comp.get("by_column") or []
    usage_values = sorted({c.get("usage") or "—" for c in all_cols} - {"—"})
    key_vars = metrics.get("key_vars") or []

    dd = {"fontSize": "11px"}
    filter_row = html.Div([
        html.Span("FILTER", style={"fontSize": "10px", "fontWeight": "700",
                                   "color": "#64748b", "marginRight": "4px"}),
        dcc.Dropdown(id=f"dqd-{TAB}-scope", clearable=False, value="all",
                     options=[{"label": "All columns", "value": "all"},
                              {"label": "Key columns only", "value": "key"},
                              {"label": "Non-key columns", "value": "non_key"}],
                     style=dict(dd, width="170px")),
        dcc.Dropdown(id=f"dqd-{TAB}-sev", clearable=False, value="all",
                     options=[{"label": "All severities", "value": "all"},
                              {"label": "High (>10%)", "value": "High"},
                              {"label": "Medium (1–10%)", "value": "Medium"},
                              {"label": "Low (≤1%)", "value": "Low"},
                              {"label": "No missings (0%)", "value": "No Missings"}],
                     style=dict(dd, width="160px")),
        dcc.Dropdown(id=f"dqd-{TAB}-dtype", clearable=False, value="all",
                     options=[{"label": "All types", "value": "all"},
                              {"label": "Numeric", "value": "Numeric"},
                              {"label": "Text", "value": "Text"},
                              {"label": "Date", "value": "Date"}],
                     style=dict(dd, width="120px")),
        dcc.Dropdown(id=f"dqd-{TAB}-usage", clearable=False, value="all",
                     options=([{"label": "All usages", "value": "all"}] +
                              [{"label": u, "value": u} for u in usage_values]),
                     style=dict(dd, width="170px")),
        html.Span(id=f"dqd-{TAB}-filter-count",
                  style={"fontSize": "10px", "color": "#64748b", "marginLeft": "auto"}),
        html.Button("× Clear matrix drilldown", id=f"dqd-{TAB}-mig-clear", n_clicks=0,
                    style={"fontSize": "10px", "padding": "3px 10px",
                           "border": "1px dashed #cbd5e1", "background": "transparent",
                           "borderRadius": "14px", "color": "#64748b",
                           "cursor": "pointer"}),
    ], style={"display": "flex", "gap": "8px", "alignItems": "center",
              "flexWrap": "wrap", "marginTop": "10px"})

    quarters = metrics.get("quarters") or []
    q24 = (metrics.get("port24") or {}).get("quarters") or []
    qbar = question_bar(
        TAB,
        [{"value": "q1", "label": Q_META["q1"]["label"]},
         {"value": "q2", "label": Q_META["q2"]["label"]}],
        default="q1")
    q2_caption = (f"Cross-portfolio: fixed pair — Port 2024 "
                  f"{q_label(q24[-1] if q24 else '')} → Port 2025 "
                  f"{q_label(quarters[-1] if quarters else '')} "
                  "(year-end snapshots)")
    controls = html.Div([
        html.Div(quarter_pair_picker(TAB, quarters,
                                     metrics.get("prior_quarter"),
                                     metrics.get("latest_quarter")),
                 id=f"dqd-{TAB}-q1-row"),
        html.Div(q2_caption, id=f"dqd-{TAB}-q2-row",
                 style={"display": "none"}),
        filter_row,
    ], style=SECTION)

    table = dash_table.DataTable(
        id=f"dqd-{TAB}-table",
        columns=[
            {"name": "Variable", "id": "column"},
            {"name": "Missing %", "id": "missing_pct", "type": "numeric"},
            {"name": "Δ vs baseline (pp)", "id": "delta_pp", "type": "numeric"},
            {"name": "Trend (8Q)", "id": "trend"},
            {"name": "Severity", "id": "severity"},
            {"name": "Missing Records", "id": "missing_n", "type": "numeric"},
            {"name": "Usage", "id": "usage"},
            {"name": "Type", "id": "dtype"},
            {"name": "Key", "id": "is_key"},
        ],
        hidden_columns=["is_key"],  # drives the bold key-var style only
        sort_action="native", page_size=20,
        style_table={"overflowX": "auto"},
        style_cell={"fontSize": "11px", "fontFamily": "inherit", "padding": "5px 10px",
                    "textAlign": "left", "maxWidth": "220px", "overflow": "hidden",
                    "textOverflow": "ellipsis"},
        style_header={"fontSize": "10px", "fontWeight": "700",
                      "textTransform": "uppercase", "color": "#64748b",
                      "background": "#f8fafc", "border": "none"},
        style_data={"border": "none", "borderBottom": "1px solid #f1f5f9"},
        style_data_conditional=(
            [{"if": {"filter_query": "{is_key} = 1", "column_id": "column"},
              "fontWeight": "700", "color": "#0f172a"}] +
            [{"if": {"filter_query": f'{{severity}} = "{name}"', "column_id": "severity"},
              "color": tone, "fontWeight": "600"}
             for name, tone in MISSING_BUCKET_TONES.items()] +
            [{"if": {"filter_query": "{delta_pp} > 0", "column_id": "delta_pp"},
              "color": "#dc2626"},
             {"if": {"filter_query": "{delta_pp} < 0", "column_id": "delta_pp"},
              "color": "#16a34a"}]),
    )

    return [
        html.Div([
            html.H2(["Completeness Dashboard — ",
                     html.Span(q_label(cq), id=f"dqd-{TAB}-title-q")],
                    style={"margin": "0 0 6px", "fontSize": "20px"}),
            html.P("Monitor missing data patterns by variable, segment, source, and data "
                   "type. Key variables (flagged in schema) are shown in bold.",
                   style={"margin": 0, "color": "#64748b", "fontSize": "13px"}),
        ], style=SECTION),

        dcc.Store(id=f"dqd-{TAB}-mig-sel", data=[]),
        qbar,
        controls,

        html.Div("Portfolio Snapshot — reference values (not filtered)",
                 style={"fontSize": "10px", "fontWeight": "700", "color": "#64748b",
                        "textTransform": "uppercase", "letterSpacing": ".05em",
                        "marginBottom": "6px"}),
        html.Div(id=f"dqd-{TAB}-headline"),
        html.Div([
            html.Span(id=f"dqd-{TAB}-buckets-title",
                      style={"fontSize": "10px", "fontWeight": "700",
                             "color": "#64748b", "textTransform": "uppercase",
                             "letterSpacing": ".05em"}),
            help_tip(SEVERITY_HELP),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}),
        html.Div(id=f"dqd-{TAB}-buckets"),

        html.Div([
            html.Div([
                html.Div(["Column-Avg Completeness % Over Time (filtered) ",
                          html.Span(id=f"dqd-{TAB}-lens")], style=SECTION_TITLE),
                html.Div("Plain average across the filtered columns — the headline "
                         "KPI above is record-weighted, so the two can differ.",
                         style={"fontSize": "10px", "color": "#94a3b8",
                                "marginBottom": "6px"}),
                dcc.Graph(id=f"dqd-{TAB}-chart-trend", config=GRAPH_CFG,
                          style={"height": "250px"}),
            ], style=SECTION_IN_GRID),
            html.Div([
                html.Div("Missing % Over Time — Per Key Variable (ignores filters)",
                         style=SECTION_TITLE),
                html.Div([
                    html.Span("Variable", style={"fontSize": "11px", "color": "#64748b",
                                                 "fontWeight": "600"}),
                    dcc.Dropdown(id=f"dqd-{TAB}-keyvar", options=key_vars,
                                 value=key_vars[0] if key_vars else None,
                                 clearable=False,
                                 style={"width": "220px", "fontSize": "11px"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                          "marginBottom": "8px"}),
                dcc.Graph(id=f"dqd-{TAB}-chart-keyvar", config=GRAPH_CFG,
                          style={"height": "250px"}),
            ], style=SECTION_IN_GRID),
        ], style=GRID2),

        html.Div([
            html.Div([
                html.Div("Missing Data by Severity (filtered)", style=SECTION_TITLE),
                html.Div([
                    dcc.Graph(id=f"dqd-{TAB}-chart-donut", config=GRAPH_CFG,
                              style={"width": "200px", "height": "200px",
                                     "flexShrink": "0"}),
                    html.Div(id=f"dqd-{TAB}-sev-table", style={"flex": "1",
                                                               "minWidth": "0"}),
                ], style={"display": "flex", "gap": "16px", "alignItems": "center"}),
                html.Div(MISSING_BUCKET_NOTE, style=dict(MUTED, marginTop="6px",
                                                         fontSize="10px")),
            ], style=SECTION_IN_GRID),
            html.Div([
                html.Div("Pareto — Top Columns by Missing Records (filtered)",
                         style=SECTION_TITLE),
                html.Div("Which columns account for the bulk of all missing values? "
                         "Cumulative line tracks the % concentration.",
                         style={"fontSize": "11px", "color": "#64748b",
                                "marginBottom": "8px"}),
                dcc.Graph(id=f"dqd-{TAB}-chart-pareto", config=GRAPH_CFG,
                          style={"height": "330px"}),
            ], style=SECTION_IN_GRID),
        ], style=GRID2),

        html.Div([
            html.Div("Missing Values Migration Matrix", style=SECTION_TITLE),
            html.Div(id=f"dqd-{TAB}-mig-subtitle",
                     style={"fontSize": "11px", "color": "#64748b", "marginBottom": "4px"}),
            html.Div(["Rows = missing-value bucket in the prior snapshot. Columns = bucket "
                      "in the current snapshot. Cells ",
                      html.Strong("above", style={"color": "#16a34a"}),
                      " the diagonal = improved. ",
                      html.Strong("Below", style={"color": "#dc2626"}),
                      " the diagonal = worsened. Diagonal = same bucket. ",
                      html.Span("💡 Click a cell to toggle it in the drilldown selection.",
                                style={"color": "#9a3412", "fontWeight": "600"})],
                     style={"fontSize": "11px", "color": "#64748b", "marginBottom": "14px"}),
            html.Div([
                html.Div(id=f"dqd-{TAB}-mig-matrix"),
                html.Div(id=f"dqd-{TAB}-mig-summary"),
            ], style={"display": "grid", "gridTemplateColumns": "2fr 1fr", "gap": "16px",
                      "alignItems": "start"}),
        ], style=SECTION),

        html.Div([
            html.Div(id=f"dqd-{TAB}-table-title", style=SECTION_TITLE),
            table,
        ], style=SECTION),

        html.Div([
            html.Div([
                html.Div(["By Business Segment ",
                          html.Span("· all columns, ignores the filters above",
                                    style={"fontSize": "9px", "fontWeight": "500",
                                           "color": "#94a3b8"})], style=SECTION_TITLE),
                html.Div(id=f"dqd-{TAB}-seg-table"),
            ], style=SECTION_IN_GRID),
            html.Div([
                html.Div("By Data Type (follows filters)", style=SECTION_TITLE),
                html.Div(id=f"dqd-{TAB}-type-table"),
            ], style=SECTION_IN_GRID),
            html.Div([
                html.Div(["By Source System ",
                          html.Span("· all columns, ignores the filters above",
                                    style={"fontSize": "9px", "fontWeight": "500",
                                           "color": "#94a3b8"})], style=SECTION_TITLE),
                html.Div(id=f"dqd-{TAB}-src-table"),
            ], style=SECTION_IN_GRID),
        ], style=GRID3),

        *_extra_segments(metrics),
    ]


# ── Callbacks ─────────────────────────────────────────────────────────────

def register_callbacks(app, metrics: dict):
    quarters = metrics.get("quarters") or []

    @app.callback(
        Output(f"dqd-{TAB}-q1-row", "style"),
        Output(f"dqd-{TAB}-q2-row", "style"),
        Output(f"dqd-{TAB}-question-desc", "children"),
        Output(f"dqd-{TAB}-question-detail", "children"),
        Input(f"dqd-{TAB}-question", "value"),
    )
    def _toggle_question_rows(question):
        meta = Q_META.get(question or "q1") or Q_META["q1"]
        show = {"display": "block"}
        cap = {"fontSize": "11px", "color": "#0f172a", "fontFamily": "monospace"}
        hid = {"display": "none"}
        if question == "q2":
            return hid, cap, meta["desc"], meta["detail"]
        return show, hid, meta["desc"], meta["detail"]

    @app.callback(
        Output(f"dqd-{TAB}-mig-sel", "data"),
        Input({"type": "dqd-comp-mig", "index": ALL}, "n_clicks"),
        Input(f"dqd-{TAB}-mig-clear", "n_clicks"),
        Input(f"dqd-{TAB}-question", "value"),
        State(f"dqd-{TAB}-mig-sel", "data"),
        prevent_initial_call=True,
    )
    def _toggle_mig(cell_clicks, clear_clicks, question, sel):
        trig = ctx.triggered_id
        if trig == f"dqd-{TAB}-question":
            return []  # a selection keyed to the other pair would mislead
        if trig == f"dqd-{TAB}-mig-clear":
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
        Output(f"dqd-{TAB}-headline", "children"),
        Output(f"dqd-{TAB}-buckets-title", "children"),
        Output(f"dqd-{TAB}-buckets", "children"),
        Output(f"dqd-{TAB}-chart-trend", "figure"),
        Output(f"dqd-{TAB}-chart-donut", "figure"),
        Output(f"dqd-{TAB}-sev-table", "children"),
        Output(f"dqd-{TAB}-chart-pareto", "figure"),
        Output(f"dqd-{TAB}-table", "data"),
        Output(f"dqd-{TAB}-table-title", "children"),
        Output(f"dqd-{TAB}-mig-subtitle", "children"),
        Output(f"dqd-{TAB}-mig-matrix", "children"),
        Output(f"dqd-{TAB}-mig-summary", "children"),
        Output(f"dqd-{TAB}-seg-table", "children"),
        Output(f"dqd-{TAB}-type-table", "children"),
        Output(f"dqd-{TAB}-src-table", "children"),
        Output(f"dqd-{TAB}-filter-count", "children"),
        Output(f"dqd-{TAB}-lens", "children"),
        Output(f"dqd-{TAB}-title-q", "children"),
        Input(f"dqd-{TAB}-question", "value"),
        Input(f"dqd-{TAB}-prior-q", "value"),
        Input(f"dqd-{TAB}-current-q", "value"),
        Input(f"dqd-{TAB}-scope", "value"),
        Input(f"dqd-{TAB}-sev", "value"),
        Input(f"dqd-{TAB}-dtype", "value"),
        Input(f"dqd-{TAB}-usage", "value"),
        Input(f"dqd-{TAB}-mig-sel", "data"),
    )
    def _update(question, prior_q, current_q, scope, sev, dtype, usage, mig_sel):
        question = question or "q1"
        pair = _resolve_pair(metrics, question, prior_q, current_q)
        cq = pair["current_q"] or metrics["latest_quarter"]
        comp = get_q(metrics, cq).get("completeness") or {}
        all_cols = comp.get("by_column") or []

        baseline_cols = pair["prior"] if not pair["invalid"] else []
        baseline_by_col = {r["column"]: r.get("missing_pct") for r in baseline_cols}
        # record-weighted, same basis as the headline KPI (was a column average)
        baseline_overall = (pair["prior_overall"]
                            if not pair["invalid"] else None)
        bl_label = f"vs {pair['prior_label']}"

        mig_var_set = _compute_mig_var_set(mig_sel, pair)

        # In Q2 the Port 2024 rows are thin (no usage/dtype) — evaluate the
        # column filters on the Port 2025 snapshot per column name and apply
        # the verdict to both sides.
        cur_meta = {r["column"]: r for r in (pair.get("current") or [])}

        def meta_row(r):
            if question == "q2":
                return cur_meta.get(r.get("column"), r)
            return r

        def filt(r):
            if mig_var_set is not None and r.get("column") not in mig_var_set:
                return False
            return _passes_filter(meta_row(r), scope, sev, dtype, usage, None)

        # the matrix universe applies the column filters but NOT the drilldown
        def filt_no_mig(r):
            return _passes_filter(meta_row(r), scope, sev, dtype, usage, None)

        filtered = sorted([c for c in all_cols if filt(c)],
                          key=lambda r: -(r.get("missing_pct") or 0))

        # ── Headline KPIs ──
        overall = comp.get("overall_pct")
        lens_delta = (round(overall - baseline_overall, 2)
                      if overall is not None and baseline_overall is not None else None)
        if lens_delta is None:
            delta_el = None
        elif lens_delta == 0:
            delta_el = html.Span(f"— {bl_label}", style={"color": "#6b7280"})
        else:
            up = lens_delta > 0
            delta_el = html.Span(
                f"{'▲ +' if up else '▼ '}{fmt(lens_delta, 2)}pp {bl_label}",
                style={"color": "#16a34a" if up else "#dc2626", "fontWeight": "600"})
        n_key = sum(1 for c in all_cols if c.get("is_key_var"))
        headline = kpi_grid([
            kpi_card("Overall Completeness", pct(overall, 2), "all columns",
                     delta=delta_el),
            kpi_card("Total Records", fmt_n(comp.get("total_records")),
                     "this snapshot"),
            kpi_card("Total Columns", fmt_n(comp.get("columns_analyzed")),
                     f"{fmt_n(n_key)} flagged as key"),
        ], 3)

        # ── Severity-bucket KPI row (single row; follows the column filter) ──
        # Canonical buckets (No Missings / Low / Medium / High) from the shared
        # missing_bucket — same source as the matrix, donut, filter and table.
        # Severity is excluded from the pool filter — these cards ARE the
        # severity breakdown, so filtering by severity would zero them out.
        def passes_no_sev(r):
            return _passes_filter(meta_row(r), scope, "all", dtype, usage, None)

        def bucket_counts(cols):
            cnt = {b: 0 for b in MISSING_BUCKETS}
            for c in cols:
                cnt[missing_bucket(c.get("missing_pct"))] += 1
            return cnt

        kpi_pool = [c for c in all_cols if passes_no_sev(c)]
        bl_pool = [c for c in baseline_cols if passes_no_sev(c)]
        cur_cnt = bucket_counts(kpi_pool)
        bl_cnt = bucket_counts(bl_pool) if bl_pool else None
        n_pool = len(kpi_pool)
        scope_label = {"key": "key", "non_key": "non-key"}.get(scope, "all")

        # No Missings is good when it grows; Low/Medium/High are bad when they grow.
        bucket_spec = [(b, MISSING_BUCKET_TONES[b], b == "No Missings")
                       for b in MISSING_BUCKETS]

        def bucket_delta(name, good_up):
            if not bl_cnt:
                return None
            d = cur_cnt[name] - bl_cnt[name]
            if d == 0:
                return html.Span(f"— {bl_label}", style={"color": "#6b7280",
                                                         "fontSize": "10px"})
            up = d > 0
            color = "#16a34a" if up == good_up else "#dc2626"
            return html.Span(f"{'▲ +' if up else '▼ '}{d} cols {bl_label}",
                             style={"color": color, "fontSize": "10px"})

        buckets = kpi_grid([
            kpi_card(name, fmt_n(cur_cnt[name]), f"of {n_pool} {scope_label} cols",
                     color=tone, accent=tone, delta=bucket_delta(name, good_up))
            for name, tone, good_up in bucket_spec], 4)

        dtype_usage_note = ""
        if dtype != "all" or usage != "all":
            bits = [b for b in (dtype if dtype != "all" else None,
                                usage if usage != "all" else None) if b]
            dtype_usage_note = " · " + " · ".join(bits)
        buckets_title = (f"Missing-Data Severity — {scope_label} columns "
                         f"(follows filter{dtype_usage_note})")

        # ── Filtered completeness trend (column-avg; trailing window around
        #    the selected pair, pair endpoints marked) ──
        traces, all_labels, yvals = [], [], []
        if question == "q2":
            t24 = _filtered_comp_ts(metrics, "port24", filt)
            t25 = _filtered_comp_ts(metrics, "port25", filt)
            if t24:
                traces.append(line_trace([r["label"] for r in t24],
                                         [r["value"] for r in t24],
                                         "Port 2024", P24_COLOR))
                all_labels += [r["label"] for r in t24]
            traces.append(line_trace([r["label"] for r in t25],
                                     [r["value"] for r in t25],
                                     "Port 2025", P25_COLOR))
            all_labels += [r["label"] for r in t25]
            yvals = [r["value"] for r in (t24 + t25) if r["value"] is not None]
        else:
            win = _trend_window(metrics, pair)
            t25 = [r for r in _filtered_comp_ts(metrics, "port25", filt)
                   if r["quarter"] in win]
            traces.append(line_trace([r["label"] for r in t25],
                                     [r["value"] for r in t25],
                                     "Port 2025", P25_COLOR))
            all_labels = [r["label"] for r in t25]
            yvals = [r["value"] for r in t25 if r["value"] is not None]
        y_lo = max(0, min(yvals) - 2) if yvals else 0
        trend_fig = _trend_fig(traces, all_labels, pair, y_range=[y_lo, 101])

        # ── Severity donut + table (canonical buckets, derived from missing %) ──
        # Worst-first so the donut and table read High → No Missings.
        sev_labels = list(reversed(MISSING_BUCKETS))  # High, Medium, Low, No Missings
        sev_counts = {}
        for c in filtered:
            b = missing_bucket(c.get("missing_pct"))
            sev_counts[b] = sev_counts.get(b, 0) + 1
        donut = go.Figure()
        if filtered:
            donut.add_trace(go.Pie(
                values=[sev_counts.get(s, 0) for s in sev_labels],
                labels=sev_labels, hole=0.62, sort=False,
                marker={"colors": [MISSING_BUCKET_TONES[s] for s in sev_labels]},
                # No on-slice labels / leader lines — they overflow the card on
                # tiny slices; the adjacent table is the legend and carries the %.
                textinfo="none",
                hovertemplate="%{label}: %{value} cols (%{percent})<extra></extra>"))
        donut.update_layout(
            margin={"t": 8, "r": 8, "b": 8, "l": 8}, height=200,
            paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
            annotations=[{"text": f"{len(filtered)}<br>cols", "showarrow": False,
                          "font": {"size": 13, "color": "#475569"}}])
        tot = len(filtered) or 1
        sev_table = simple_table(
            ["Severity", "Columns", "%"],
            [html.Tr([td(_sev_badge(s)), td(fmt_n(sev_counts.get(s, 0))),
                      td(pct(sev_counts.get(s, 0) / tot * 100))]) for s in sev_labels])

        # ── Pareto ──
        by_missing_n = sorted(filtered, key=lambda r: -(r.get("missing_n") or 0))[:15]
        pareto = go.Figure()
        full_names, x_disp = [], []
        if by_missing_n:
            total_missing = sum(r.get("missing_n") or 0 for r in filtered) or 1
            running, cumulative = 0, []
            for r in by_missing_n:
                running += r.get("missing_n") or 0
                cumulative.append(running / total_missing * 100)
            # Use the FULL (unique) names as the categorical x so two columns
            # that share a truncated prefix (e.g. "Principal Repayment
            # Frequency" vs "… Type") don't collapse onto one position and
            # corrupt the cumulative line. Truncation is display-only, via
            # ticktext.
            full_names = [str(r["column"]) for r in by_missing_n]
            x_disp = [n if len(n) <= 18 else n[:17] + "…" for n in full_names]
            pareto.add_trace(go.Bar(
                x=full_names,
                y=[r.get("missing_n") for r in by_missing_n],
                customdata=full_names,
                marker={"color": ["#dc2626" if r.get("is_key_var") else "#94a3b8"
                                  for r in by_missing_n]},
                name="Missing records",
                hovertemplate="<b>%{customdata}</b><br>%{y:,} missing<extra></extra>"))
            pareto.add_trace(go.Scatter(
                x=full_names, y=cumulative, yaxis="y2", customdata=full_names,
                mode="lines+markers", line={"color": "#0f1d35", "width": 2},
                marker={"size": 4}, name="Cumulative %",
                hovertemplate="<b>%{customdata}</b><br>Cumulative: %{y:.1f}%"
                              "<extra></extra>"))
        pareto.update_layout(
            margin={"t": 10, "r": 60, "b": 120, "l": 50}, height=330,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"type": "category", "tickangle": -40, "tickfont": {"size": 9},
                   "categoryorder": "array", "categoryarray": full_names,
                   "tickmode": "array", "tickvals": full_names, "ticktext": x_disp},
            yaxis={"title": "Missing records", "gridcolor": "#f1f5f9",
                   "tickfont": {"size": 9}},
            yaxis2={"title": "Cumulative %", "overlaying": "y", "side": "right",
                    "range": [0, 105], "showgrid": False, "tickfont": {"size": 9}},
            legend={"orientation": "h", "y": 1.12, "font": {"size": 9}})

        # ── Top-N table data ──
        spark_qs = quarters[-8:]
        spark_cache = {}
        for q in spark_qs:
            cols = (get_q(metrics, q).get("completeness") or {}).get("by_column") or []
            spark_cache[q] = {c["column"]: c.get("missing_pct") for c in cols}

        def row_spark(col):
            vals = [spark_cache[q].get(col) for q in spark_qs]
            return spark([v for v in vals if v is not None])

        table_data = []
        for r in filtered:
            bl = baseline_by_col.get(r["column"])
            delta_pp = (round(float(r.get("missing_pct") or 0) - float(bl), 2)
                        if bl is not None else None)
            table_data.append({
                "column": str(r.get("column")),
                "is_key": 1 if r.get("is_key_var") else 0,
                "missing_pct": round(float(r.get("missing_pct") or 0), 2),
                "delta_pp": delta_pp,
                "trend": row_spark(r.get("column")),
                "severity": missing_bucket(r.get("missing_pct")),
                "missing_n": r.get("missing_n"),
                "usage": r.get("usage") or "—",
                "dtype": dtype_bucket(r),
            })
        table_title = (f"Missing % by Variable — {len(filtered)} filtered columns — "
                       f"{pair['current_label']} (Δ {bl_label})")

        # ── Migration matrix ──
        if pair["invalid"]:
            matrix_el = empty_note(f"⚠ {pair['invalid']} Adjust the snapshot "
                                   "pair above to populate the matrix.")
            summary_el = ""
        elif pair["prior"] or pair["current"]:
            prior_scoped = [r for r in pair["prior"] if filt_no_mig(r)]
            cur_scoped = [r for r in pair["current"] if filt_no_mig(r)]
            M = _build_migration_matrix(prior_scoped, cur_scoped)
            extra = ("Type/usage filters are evaluated on the Port 2025 snapshot "
                     "(Port 2024 column metadata is limited to missing % and "
                     "severity)." if question == "q2" else None)
            matrix_el = _matrix_component(M, pair, mig_sel, extra_note=extra)
            summary_el = _matrix_summary(M)
        else:
            matrix_el = empty_note("No completeness snapshots available for this "
                                   "comparison. (Port 2024 per-column data is "
                                   "required for the cross-portfolio benchmark.)")
            summary_el = ""

        # ── Aggregate breakdowns ──
        seg_rows = [html.Tr([
            td(s.get("segment")), td(pct(s.get("completeness_pct"))),
            td(pct(s.get("missing_pct"))),
        ]) for s in (comp.get("by_segment") or [])]
        seg_table = simple_table(["Segment", "Completeness %", "Missing %"], seg_rows)

        type_agg = {}
        for c in filtered:
            t = dtype_bucket(c)
            a = type_agg.setdefault(t, {"n": 0, "sum_miss": 0.0})
            a["n"] += 1
            a["sum_miss"] += float(c.get("missing_pct") or 0)
        type_rows = []
        for t in sorted(type_agg):
            a = type_agg[t]
            miss = a["sum_miss"] / a["n"] if a["n"] else 0
            type_rows.append(html.Tr([
                td([t, html.Span(f" ({a['n']})", style={"fontSize": "9px",
                                                        "color": "#64748b"})]),
                td(pct(100 - miss)), td(pct(miss))]))
        type_table = (simple_table(["Type", "Completeness %", "Missing %"], type_rows)
                      if type_rows else empty_note("No matching columns."))

        src_rows = [html.Tr([
            td(s.get("source")), td(pct(s.get("completeness_pct"))),
            td(pct(s.get("missing_pct"))),
        ]) for s in (comp.get("by_source") or [])]
        src_table = simple_table(["Source", "Completeness %", "Missing %"], src_rows)

        count_txt = f"{len(filtered)} / {len(all_cols)} columns"
        if mig_var_set is not None:
            count_txt += f" · matrix drilldown: {len(mig_sel)} cell(s), {len(mig_var_set)} var(s)"
        meta = Q_META.get(question) or Q_META["q1"]
        chip = question_chip(meta["label"],
                             f"{pair['prior_label']} → {pair['current_label']}",
                             meta["color"])

        return (headline, buckets_title, buckets, trend_fig, donut, sev_table,
                pareto, table_data, table_title, pair["label"], matrix_el, summary_el,
                seg_table, type_table, src_table, count_txt, chip,
                pair["current_label"])

    @app.callback(
        Output(f"dqd-{TAB}-chart-keyvar", "figure"),
        Input(f"dqd-{TAB}-keyvar", "value"),
        Input(f"dqd-{TAB}-question", "value"),
        Input(f"dqd-{TAB}-prior-q", "value"),
        Input(f"dqd-{TAB}-current-q", "value"),
    )
    def _keyvar_trend(var, question, prior_q, current_q):
        question = question or "q1"
        pair = _resolve_pair(metrics, question, prior_q, current_q)
        s25 = ((metrics.get("time_series") or {})
               .get("missing_by_variable") or {}).get(var) or []
        traces, all_labels = [], []
        if question == "q2":
            s24 = (((metrics.get("port24") or {}).get("time_series") or {})
                   .get("missing_by_variable") or {}).get(var) or []
            if s24:
                traces.append(line_trace(
                    [q_label(r.get("quarter")) for r in s24],
                    [r.get("missing_pct") for r in s24], "Port 2024", P24_COLOR))
                all_labels += [q_label(r.get("quarter")) for r in s24]
        else:
            win = _trend_window(metrics, pair)
            s25 = [r for r in s25 if r.get("quarter") in win]
        traces.append(line_trace(
            [q_label(r.get("quarter")) for r in s25],
            [r.get("missing_pct") for r in s25], "Port 2025", P25_COLOR))
        all_labels += [q_label(r.get("quarter")) for r in s25]
        return _trend_fig(traces, all_labels, pair, y_mode="tozero")
