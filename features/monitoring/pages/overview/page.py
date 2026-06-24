"""General monitoring overview page for the dashboard.

Ported from ``integrated:pages/monitoring_overview_layout.py`` into the
main-branch page structure.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from .....components.charts import build_pd_time_series_xaxis
from .....components.filters import build_range_controls
from .....data.analytics.calculations import filter_pd_periods_by_range, pd_tone_class
from .....data.analytics.overview import (
    RAG_COLUMNS,
    RAG_SCORE,
    build_overview_rows,
    display_rag,
    effective_rag,
    filter_overview_rows,
    heatmap_rows,
    overview_filter_options,
    overview_summary,
    top_findings,
)

CONTENT_ID = "overview-content"
PERIOD_ID = "overview-monitoring-period"
MODEL_GROUP_ID = "overview-model-group"
MODEL_ID = "overview-model"
SEGMENT_ID = "overview-segment"
RAG_TREND_METRIC_ID = "overview-rag-trend-metric"
OVERVIEW_SUBNAV_ID = "overview-subnav"
RANGE_STORE_ID = "overview-range-store"
RAG_TREND_RANGE_KEY = "overview_rag_trend"

RAG_LABELS = {
    "Overall RAG": "Model RAG (Post Subjective Review)",
}
RAG_TREND_OPTIONS = list(RAG_COLUMNS)
_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
RAG_DESCRIPTIONS = {
    "Calibration Conservatism RAG": "The objective is to assess the magintude and direction of prediction error to conclude on the level of conservatism.",
    "Discriminatory Power RAG": "Tests whether the model estimates are rank ordering the counter parties by the actual risk observed.",
    "Performance RAG": "Also called Model RAG (initial), it is based on the results of tests applied at the modelled outcomes.",
    "Overall RAG": "Reflects the impact of any subjective overlay with appropiate justification.",
    "Pre-Mitigation RAG": "Obtained from a trend of Model RAG (post subjective review) from the current and past monitoring outcomes. For ST models, only the current one will be considered.",
    "Post-Mitigation RAG": "Based on the residual risk of the model. The residual risk is judgement based and includes manual overlays, compensating controls, etc.",
}
RAG_MARKER_COLORS = {
    "Green": "#16a34a",
    "Amber": "#d97706",
    "Red": "#dc2626",
    "N/A": "#94a3b8",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rag_label(column: str) -> str:
    return RAG_LABELS.get(column, column)


def _dropdown_options(values: list[str], labels: dict[str, str] | None = None) -> list[dict]:
    labels = labels or {}
    return [{"label": labels.get(value, value), "value": value} for value in values]


def _subnav_link(section_id: str, label: str, active: bool = False) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


def _build_overview_subnav() -> html.Div:
    return html.Div(
        id=OVERVIEW_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-summary", "Overview", active=True),
                            _subnav_link("overview-heatmap", "Model RAG Heatmap"),
                            _subnav_link("overview-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-top-findings", "Top Findings"),
                            _subnav_link("overview-governance-summary", "Governance Summary"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _rag_visual_tone(rag: str | None) -> str:
    if rag == "Neutral":
        return "neutral"
    return "fallback" if rag == "N/A" else pd_tone_class(effective_rag(rag))


def _rag_marker_color(rag: str | None) -> str:
    return RAG_MARKER_COLORS["N/A"] if rag == "N/A" else RAG_MARKER_COLORS.get(effective_rag(rag), "#94a3b8")


def _rag_badge(rag: str) -> html.Span:
    label = "No findings" if rag == "Neutral" else display_rag(rag)
    return html.Span(
        className=f"overview-rag-badge overview-rag-{_rag_visual_tone(rag)}",
        title=label,
        **{"aria-label": label},
    )


def _rag_legend_item(rag: str, label: str, description: str) -> html.Div:
    return html.Div(
        className="overview-rag-legend-item",
        children=[
            _rag_badge(rag),
            html.Div(
                children=[
                    html.Strong(label),
                    html.Span(description),
                ]
            ),
        ],
    )


def _rag_heatmap_legend() -> html.Div:
    return html.Div(
        className="overview-rag-legend",
        children=[
            _rag_legend_item("Green", "Green", "In tolerance."),
            _rag_legend_item("Amber", "Amber", "Review signal."),
            _rag_legend_item("Red", "Red", "Finding / breach."),
            _rag_legend_item("N/A", "Fallback Amber", "No modeled RAG available; counted and trended as Amber."),
        ],
    )


def _rag_header(column: str) -> html.Th:
    if column not in RAG_COLUMNS:
        return html.Th(column)
    description = RAG_DESCRIPTIONS[column]
    return html.Th(
        html.Span(
            className="overview-rag-header",
            children=[
                html.Span(_rag_label(column)),
                html.Span(
                    className="overview-help",
                    children=[
                        html.Span("?", className="overview-help-chip", title=description, **{"aria-label": description}),
                        html.Span(description, className="overview-help-tooltip", role="tooltip"),
                    ],
                ),
            ],
        )
    )


def _summary_card(
    title: str,
    value: int | str,
    subtitle: str,
    rag: str | None = "N/A",
    visual_rag: str | None = None,
) -> html.Article:
    tone_class = pd_tone_class(rag) if rag else None
    card_class = f"pd-test-card pd-test-{tone_class} overview-summary-card" if tone_class else "pd-test-card overview-summary-card overview-summary-card-neutral"
    marker_rag = visual_rag or rag
    status = (
        html.Div(
            _rag_badge(marker_rag),
            className=f"pd-test-status pd-test-status-{pd_tone_class(effective_rag(rag))}",
        )
        if rag
        else None
    )
    return html.Article(
        className=card_class,
        children=[
            html.Div(
                className="pd-test-card-heading",
                children=[
                    html.Div([
                        html.Span("Overview"),
                        html.Div(html.H4(title), className="pd-card-title-row"),
                    ]),
                    status,
                ],
            ),
            html.Div(str(value), className="pd-test-value"),
            html.Div(subtitle, className="pd-test-meta"),
        ],
    )


def _rag_heatmap_table(rows: list[dict]) -> html.Div:
    columns = ["Model Group", "Model", *RAG_COLUMNS]
    return html.Div(
        className="overview-table-wrap",
        children=[
            html.Table(
                children=[
                    html.Thead(html.Tr([_rag_header(column) for column in columns])),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(row[column]) if column not in RAG_COLUMNS else html.Td(_rag_badge(row[column]))
                                    for column in columns
                                ]
                            )
                            for row in rows
                        ]
                    ),
                ]
            ),
            _rag_heatmap_legend(),
        ],
    )


def _findings_table(rows: list[dict]) -> html.Div:
    columns = ["Monitoring Period", "Model Group", "Model", "Metric", "Current", "Threshold"]
    if not rows:
        rows = [{
            "Monitoring Period": "-",
            "Model Group": "All",
            "Model": "No heatmap findings",
            "Metric": "-",
            "Current": "-",
            "Threshold": "-",
            "RAG": "Green",
        }]
    return html.Div(
        className="overview-table-wrap overview-findings-table-wrap",
        children=[
            html.Table(
                children=[
                    html.Thead(html.Tr([html.Th(column) for column in columns])),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(_rag_badge(row["RAG"]))
                                    if column == "Current" and row["RAG"] != "Green"
                                    else html.Td(_rag_label(row[column]) if column == "Metric" else row[column])
                                    for column in columns
                                ]
                            )
                            for row in rows
                        ]
                    ),
                ]
            )
        ],
    )


def _worst_period_rag(rows: list[dict], rag_column: str) -> str:
    return max(
        (row.get(rag_column, "N/A") for row in rows),
        key=lambda rag: (RAG_SCORE.get(effective_rag(rag), 0), 0 if rag == "N/A" else 1),
        default="N/A",
    )


def _rag_trend_figure(rows: list[dict], rag_column: str, model_group: str, model_name: str, visible_periods: list[str]) -> go.Figure:
    fig = go.Figure()
    model_rows = [row for row in rows if row["Model Group"] == model_group and row["Model"] == model_name]
    model_periods = {row["Monitoring Period"] for row in model_rows}
    periods = [period for period in visible_periods if period in model_periods]
    rags = [_worst_period_rag([row for row in model_rows if row["Monitoring Period"] == period], rag_column) for period in periods]
    y_values = [RAG_SCORE.get(effective_rag(rag), 0) for rag in rags]
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=y_values,
            customdata=[display_rag(rag) for rag in rags],
            mode="lines+markers",
            name=model_name,
            line=dict(width=2.4),
            marker=dict(size=8, color=[_rag_marker_color(rag) for rag in rags], line=dict(color="#ffffff", width=1)),
            hovertemplate="Period: %{x}<br>RAG: %{customdata}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"{model_group}: {model_name}",
        height=310,
        margin=dict(l=48, r=18, t=52, b=54),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=build_pd_time_series_xaxis(periods, {"gridcolor": "#e5e7eb"}, density="compact"),
        yaxis=dict(
            tickmode="array",
            tickvals=[1, 2, 3],
            ticktext=["Green", "Amber / Fallback", "Red"],
            range=[0.8, 3.2],
            gridcolor="#e5e7eb",
        ),
    )
    return fig


def _rag_trend_graphs(rows: list[dict], rag_column: str, range_store: dict | None = None) -> html.Div:
    model_keys = sorted({(row["Model Group"], row["Model"]) for row in rows})
    trend_periods = sorted({row["Monitoring Period"] for row in rows})
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), trend_periods)
    return html.Div(
        className="overview-trend-grid",
        children=[
            html.Div(
                className="section-card overview-trend-panel",
                children=[
                    dcc.Graph(
                        figure=_rag_trend_figure(rows, rag_column, model_group, model_name, visible_periods),
                        config=_GRAPH_CONFIG,
                    )
                ],
            )
            for model_group, model_name in model_keys
        ],
    )


def _findings_summary_rag(findings: list[dict]) -> str:
    if any(effective_rag(row["RAG"]) == "Red" for row in findings):
        return "Red"
    if any(effective_rag(row["RAG"]) == "Amber" for row in findings):
        return "Amber"
    return "N/A"


# ---------------------------------------------------------------------------
# Content rendering
# ---------------------------------------------------------------------------


def render_overview_content(
    data: dict,
    overview_rows: list[dict],
    monitoring_period: str = "All",
    model_group: str = "All",
    model: str = "All",
    segment: str = "All",
    rag_trend_metric: str = "Overall RAG",
    range_store: dict | None = None,
) -> list:
    rows = filter_overview_rows(overview_rows, monitoring_period, model_group, model, segment)
    if not rows:
        return [html.Div("No overview data is available for the selected filters.", className="section-card")]

    summary = overview_summary(rows, monitoring_period)
    heat_rows = heatmap_rows(rows, monitoring_period)
    latest_period = monitoring_period if monitoring_period != "All" else max(row["Monitoring Period"] for row in rows)
    findings = top_findings(heat_rows)
    red_findings = sum(1 for row in findings if effective_rag(row["RAG"]) == "Red")
    amber_findings = sum(1 for row in findings if effective_rag(row["RAG"]) == "Amber")
    findings_rag = _findings_summary_rag(findings)
    trend_periods = sorted({row["Monitoring Period"] for row in rows})
    range_store = range_store or {}

    return [
        html.Div(
            id="overview-summary",
            children=[
                html.Div(f"Monitoring point: {latest_period}", className="overview-section-context"),
                html.Div(
                    className="overview-summary-grid",
                    children=[
                        _summary_card("Models Monitored", summary["models"], "Filtered view", None),
                        _summary_card("Red Models", summary["red"], f"Current period: {latest_period}", "Red"),
                        _summary_card("Amber Models", summary["amber"], f"Current period: {latest_period}", "Amber"),
                        _summary_card("Green Models", summary["green"], f"Current period: {latest_period}", "Green"),
                        _summary_card(
                            "Findings",
                            len(findings),
                            "Red + Amber heatmap RAGs",
                            findings_rag,
                            "Neutral" if not findings else None,
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            id="overview-heatmap",
            className="section-card",
            children=[
                html.Div("Model RAG Heatmap", className="section-title"),
                html.Div(f"RAG by model for {latest_period}.", className="pd-section-subtitle"),
                _rag_heatmap_table(heat_rows),
            ],
        ),
        html.Div(
            id="overview-rag-trend",
            className="section-card",
            children=[
                html.Div(
                    className="overview-card-heading-row",
                    children=[
                        html.Div([
                            html.Div("RAG Trend Analysis", className="section-title"),
                            html.Div(f"Period-over-period comparison of {_rag_label(rag_trend_metric)} by model.", className="pd-section-subtitle"),
                        ]),
                        dcc.Dropdown(
                            id=RAG_TREND_METRIC_ID,
                            options=_dropdown_options(RAG_TREND_OPTIONS, RAG_LABELS),
                            value=rag_trend_metric,
                            clearable=False,
                            className="monitoring-top-select overview-compact-dropdown",
                        ),
                        build_range_controls(RAG_TREND_RANGE_KEY, trend_periods, range_store.get(RAG_TREND_RANGE_KEY)),
                    ],
                ),
                _rag_trend_graphs(rows, rag_trend_metric, range_store),
            ],
        ),
        html.Div(
            id="overview-top-findings",
            className="section-card",
            children=[
                html.Div("Top Findings", className="section-title"),
                html.Div(f"Red and Amber RAGs for {latest_period}.", className="pd-section-subtitle"),
                _findings_table(findings),
            ],
        ),
        html.Div(
            id="overview-governance-summary",
            className="section-card overview-governance-card",
            children=[
                html.Div("Governance / Findings Summary", className="section-title"),
                html.P("Review Red and Amber findings."),
                html.Div(
                    className="overview-governance-tags",
                    children=[
                        html.Span(f"{red_findings} Red Findings", className="overview-tag overview-tag-red"),
                        html.Span(f"{amber_findings} Amber Findings", className="overview-tag overview-tag-amber"),
                    ],
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Stores & layout entry points
# ---------------------------------------------------------------------------


def build_stores() -> list:
    """``dcc.Store`` components backing this page's range state."""
    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
    ]


def build_layout() -> list:
    """Registry entry point: build the page from the loaded dashboard data."""
    from ...data_access import PD_PERFORMANCE_DATA

    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Top bar + main content for the Overview page."""
    overview_rows = build_overview_rows(data)
    options = overview_filter_options(overview_rows)
    return [
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("Wholesale Portfolio Model Monitoring Dashboard", className="monitoring-dashboard-title"),
                        html.Div(
                            className="monitoring-controls",
                            children=[
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Monitoring Point", htmlFor=PERIOD_ID),
                                        dcc.Dropdown(id=PERIOD_ID, options=_dropdown_options(options["periods"]), value="All", clearable=False, className="monitoring-top-select"),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Segment", htmlFor=SEGMENT_ID),
                                        dcc.Dropdown(id=SEGMENT_ID, options=_dropdown_options(options["segments"]), value="All", clearable=False, className="monitoring-top-select"),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Specific Models", htmlFor=MODEL_ID),
                                        dcc.Dropdown(id=MODEL_ID, options=_dropdown_options(options["models"]), value="All", clearable=False, className="monitoring-top-select"),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Model Group", htmlFor=MODEL_GROUP_ID),
                                        dcc.Dropdown(id=MODEL_GROUP_ID, options=_dropdown_options(options["groups"]), value="All", clearable=False, className="monitoring-top-select"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(style={"marginTop": "12px"}, children=[_build_overview_subnav()]),
                    ],
                ),
            ],
        ),
        html.Div(
            className="content",
            children=[
                html.Div(
                    className="tab-panel active pd-performance-app",
                    children=[
                        html.Div(
                            className="pd-content-heading",
                            children=[
                                html.Div("General Model Monitoring View", className="pd-content-kicker"),
                                html.H3("Overview"),
                                html.P("Portfolio-level model monitoring summary."),
                            ],
                        ),
                        html.Div(
                            id=CONTENT_ID,
                            children=render_overview_content(data, overview_rows),
                        ),
                    ],
                )
            ],
        ),
    ]
