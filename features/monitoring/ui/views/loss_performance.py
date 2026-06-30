"""Layout for the Loss Performance page."""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from .....components.charts import build_loss_metric_trend_figure, build_loss_rag_trend_figure
from .....components import filters as shared_filters
from .....components.filters import build_chart_header
from .....data.analytics.calculations import (
    format_pd_compact_amount,
    format_pd_metric,
    fmt_n,
    pd_tone_class,
)
from ...domain.loss import (
    build_loss_period_summary,
    build_loss_rag_trend,
    get_loss_default_model,
    get_loss_model_options,
    get_loss_monitoring_point_options,
    get_loss_segments_for_model,
    get_loss_thresholds,
)
from .cards import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)

CONTENT_ID = "loss-dashboard-content"
REPORTING_CYCLE_ID = "loss-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "loss-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "loss-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "loss-reporting-cycle"
MODEL_DROPDOWN_ID = "loss-model-dropdown"
SEGMENT_DROPDOWN_ID = "loss-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "loss-monitoring-point-dropdown"
MODEL_TOGGLE_ID = "loss-model-toggle"
MODEL_MENU_ID = "loss-model-menu"
MODEL_SELECT_ALL_ID = "loss-model-select-all"
SEGMENT_TOGGLE_ID = "loss-segment-toggle"
SEGMENT_MENU_ID = "loss-segment-menu"
MONITORING_POINT_TOGGLE_ID = "loss-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "loss-monitoring-point-menu"
MODEL_FILTER_KEY = "loss-model"
SEGMENT_FILTER_KEY = "loss-segment"
MONITORING_POINT_FILTER_KEY = "loss-monitoring-point"
LOSS_SUBNAV_ID = "loss-subnav"
RANGE_STORE_ID = "loss-range-store"
PERFORMANCE_RAG_RANGE_KEY = "loss_performance_rag"
ME_PCT_RANGE_KEY = "loss_me_pct"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------------------------------------------------------------------------
# Helpers inlined from the LGD layout (private utilities)
# ---------------------------------------------------------------------------


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _build_filter(label: str, component) -> html.Div:
    return html.Div(className="monitoring-filter", children=[html.Label(label), component])


def _subnav_link(section_id: str, label: str, active: bool = False) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


def _rag_dot(rag: str) -> html.Span:
    tone = (rag or "N/A").lower().replace("/", "").replace(" ", "-")
    if tone in {"na", "n-a"}:
        tone = "neutral"
    return html.Span(
        "",
        className=f"overview-rag-badge overview-rag-{tone}",
        title=rag or "N/A",
        **{"aria-label": rag or "N/A"},
    )


def _format_value(metric: str, value: Any) -> str:
    if metric in {"ME", "RMSE", "Predicted LGD", "Actual LGD", "Recovery Rate"}:
        return format_pd_metric(value, "percent")
    if metric in {"Observations", "Defaults"}:
        return fmt_n(value)
    return format_pd_metric(value, "ratio")


def _format_delta(metric: str, current_value: Any, previous_value: Any) -> tuple[str, str]:
    if current_value is None or previous_value is None:
        return "N/A", "neutral"
    try:
        delta = float(current_value) - float(previous_value)
    except (TypeError, ValueError):
        return "N/A", "neutral"
    tone = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
    formatted = _format_value(metric, delta)
    if delta > 0 and not formatted.startswith("+"):
        formatted = f"+{formatted}"
    return formatted, tone


def _flow_connector_spans(*, incoming: bool = False, outgoing: bool = False) -> list[html.Span]:
    spans = []
    if incoming:
        spans.append(html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-in", **{"aria-hidden": "true"}))
    if outgoing:
        spans.append(html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-out", **{"aria-hidden": "true"}))
    return spans


def _flow_metric(
    label: str,
    value: Any,
    metric: str,
    rag: str,
    href: str,
    *,
    previous_value: Any = None,
    previous_period: str = "",
    incoming: bool = False,
    outgoing: bool = False,
) -> html.Article:
    change_value, change_tone = _format_delta(metric, value, previous_value)
    return html.Article(
        className=f"pd-overview-flow-node pd-overview-flow-node-{pd_tone_class(rag)}",
        children=html.A(
            className="pd-overview-flow-link",
            href=href,
            children=[
                *_flow_connector_spans(incoming=incoming, outgoing=outgoing),
                html.Span(label, className="pd-overview-flow-node-label"),
                html.Span(_format_value(metric, value), className="pd-overview-flow-node-value"),
                html.Span([_rag_dot(rag), html.Span(f" {rag}")], className="pd-overview-flow-node-note"),
                html.Span(
                    [
                        html.Span(
                            [
                                html.Span(f"Previous ({previous_period or 'No prior quarter'})"),
                                html.Strong(_format_value(metric, previous_value)),
                            ]
                        ),
                        html.Span(
                            [
                                html.Span("Change"),
                                html.Strong(change_value, className=f"lgd-flow-change lgd-flow-change-{change_tone}"),
                            ]
                        ),
                    ],
                    className="lgd-flow-node-comparison",
                ),
            ],
        ),
    )


def _flow_stage(text: str) -> html.Div:
    return html.Div(html.Span(text), className="pd-overview-flow-stage")


def _build_chart_panel(title: str, description: str, figure) -> html.Div:
    return html.Div(
        className="section-card pd-default-rate-trend-section",
        children=[
            html.Div(
                className="pd-chart-heading",
                children=[
                    html.Div(
                        className="pd-chart-heading-copy",
                        children=[html.Div(title, className="section-title"), html.Div(description, className="pd-section-subtitle")],
                    ),
                ],
            ),
            dcc.Graph(figure=figure, config=_GRAPH_CONFIG, className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium"),
        ],
    )


# ---------------------------------------------------------------------------
# Page-specific helpers
# ---------------------------------------------------------------------------


def _money(value) -> str:
    return format_pd_compact_amount(value)


def _build_loss_subnav() -> html.Div:
    return html.Div(
        id=LOSS_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("loss-overview", "Overview", active=True),
                            _subnav_link("loss-performance", "Performance"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_loss_overview_flow(summary: dict) -> html.Div:
    from .....components.kpis import (
        build_pd_overview_flow_input,
        build_pd_overview_flow_metric,
        build_pd_overview_flow_stage,
        build_pd_overview_flow_test_stack,
    )

    me_pct_rag = summary["metric_rags"].get("ME %", "N/A")
    performance_rag = summary["performance_rag"]

    flow_children = [
        html.Div(build_pd_overview_flow_stage("1.", "Component"), className="loss-flow-stage-input"),
        html.Div(build_pd_overview_flow_stage("2.", "Test"), className="loss-flow-stage-tests"),
        html.Div(build_pd_overview_flow_stage("3.", "Performance RAG"), className="loss-flow-stage-performance"),

        html.Div(
            build_pd_overview_flow_input("Loss", {"note": "1 year monitoring"}),
            className="loss-flow-input",
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric(
                    "Mean Error % 1 year", summary["current"].get("ME %"), "percent", me_pct_rag,
                    {"href": "#loss-performance"},
                ),
            ],
            {"incoming": True, "outgoing": True, "extra_class": "loss-flow-tests"},
        ),

        html.Div(
            className="loss-flow-performance",
            children=html.Article(
                className=f"pd-overview-flow-performance pd-overview-flow-performance-{pd_tone_class(performance_rag)}",
                children=[
                    html.Span("Performance RAG", className="pd-overview-flow-performance-title"),
                    html.Strong([pd_rag_dot(performance_rag), f" {performance_rag}"]),
                ],
            ),
        ),
    ]

    return html.Div(
        className="pd-overview-flow-wrap",
        children=html.Div(
            flow_children,
            className="loss-overview-flow",
            **{"aria-label": "Loss monitoring overview process flow"},
        ),
    )


# ---------------------------------------------------------------------------
# Content renderer
# ---------------------------------------------------------------------------


def render_loss_performance_content(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
    range_store: dict | None = None,
) -> list:
    range_store = range_store or {}
    summary = build_loss_period_summary(data, selected_model, selected_segment, selected_monitoring_point)
    thresholds = get_loss_thresholds(data)
    context = {
        "snapshot_quarter": summary["monitoring_point"] or "No monitoring point",
        "previous_quarter": summary["previous_monitoring_point"],
    }

    if not summary["current"]:
        return [
            html.Div(
                className="section-card pd-placeholder-card",
                children=[
                    html.Div("No Loss data", className="pd-placeholder-badge"),
                    html.Div("Loss Performance", className="pd-placeholder-title"),
                    html.P("No Loss observations are available for the selected model and segment."),
                ],
            )
        ]

    current = summary["current"]
    metric_rows = summary["metric_rows"]
    monitoring_point = summary["monitoring_point"]
    rag_trend = build_loss_rag_trend(data, metric_rows)
    rag_periods = [row["quarter"] for row in rag_trend]

    performance_cards = [
        build_pd_section_rag_card(
            "Performance RAG",
            summary["performance_rag"],
            summary["previous_performance_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
        build_pd_test_card(
            "ME %",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {
                "format": "percent",
                "card_title": "Mean Error % 1 year",
                "extra_meta_rows": [
                    {"label": "Mean Error", "value": _money(current.get("ME"))},
                    {"label": "Predicted Loss", "value": _money(current.get("Predicted Loss"))},
                    {"label": "Actual Loss", "value": _money(current.get("Actual Loss"))},
                ],
            },
        ),
    ]

    chapter_1 = html.Section(
        id="loss-rag-assignment",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "1.",
                "RAG Assignment",
                "Core monitoring view for Loss model health, where Mean Error % feeds directly into the Performance RAG.",
                options={"note": f"Monitoring point {monitoring_point}"},
            ),
        ],
    )

    overview_section = html.Section(
        id="loss-overview",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Overview",
                "Loss RAG Assignment Overview",
                "At-a-glance summary of the 1 year Loss monitoring flow from Mean Error % to Performance RAG.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            _build_loss_overview_flow(summary),
        ],
    )

    performance_section = html.Section(
        id="loss-performance",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 Performance",
                "Performance",
                "Assess predicted loss against the observed loss proxy using Mean Error %.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid", style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"}, children=performance_cards),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
                    html.Div(
                        id="loss-performance-rag-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Performance RAG Trend",
                                "Quarter-by-quarter Performance RAG shown as a simple color-coded dot timeline.",
                                PERFORMANCE_RAG_RANGE_KEY,
                                rag_periods,
                                range_store.get(PERFORMANCE_RAG_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="loss-performance-rag-trend-chart",
                                figure=build_loss_rag_trend_figure(
                                    rag_trend,
                                    monitoring_point,
                                    range_store.get(PERFORMANCE_RAG_RANGE_KEY),
                                ),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                    html.Div(
                        id="loss-me-pct-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Mean Error % Trend",
                                "Mean error percentage by monitoring point with Loss threshold shading.",
                                ME_PCT_RANGE_KEY,
                                rag_periods,
                                range_store.get(ME_PCT_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="loss-me-pct-trend-chart",
                                figure=build_loss_metric_trend_figure(metric_rows, data["monitoring_thresholds"], monitoring_point),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return [
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, performance_section]),
    ]


# ---------------------------------------------------------------------------
# Top-level page layout
# ---------------------------------------------------------------------------


def build_layout() -> list:
    """No-arg entry point for the page registry."""
    from ...data_access import PD_PERFORMANCE_DATA
    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Build the Loss page with top controls and live content."""
    from .....data.filters.filters_config import load_filter_config, model_names, segment_values
    from ...domain.loss import set_loss_metrics
    cfg = load_filter_config()
    model_options = model_names("loss")
    default_model = "all"
    segment_options = ["All", *segment_values()]
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    cycle_data = (data.get("loss_observations_by_cycle") or {}).get(default_cycle)
    if cycle_data:
        set_loss_metrics(cycle_data.get("metrics_store"), cycle_data.get("quarters"))
    else:
        set_loss_metrics(None, [])
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_options = cycle_quarters if cycle_quarters else get_loss_monitoring_point_options(data, None, "All")
    default_monitoring_point = monitoring_options[0] if monitoring_options else ""

    model_select_options = [{"label": "All models", "value": "all"}] + [{"label": name, "value": name} for name in model_options]

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
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
                                _build_filter(
                                    "Reporting Cycle",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=REPORTING_CYCLE_ID,
                                        toggle_id=REPORTING_CYCLE_TOGGLE_ID,
                                        menu_id=REPORTING_CYCLE_MENU_ID,
                                        filter_key=REPORTING_CYCLE_FILTER_KEY,
                                        options=reporting_cycle_options,
                                        value=default_cycle,
                                    ),
                                ),
                                _build_filter(
                                    "Monitoring Point",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=MONITORING_POINT_DROPDOWN_ID,
                                        toggle_id=MONITORING_POINT_TOGGLE_ID,
                                        menu_id=MONITORING_POINT_MENU_ID,
                                        filter_key=MONITORING_POINT_FILTER_KEY,
                                        options=[{"label": q, "value": q} for q in monitoring_options],
                                        value=default_monitoring_point,
                                    ),
                                ),
                                _build_filter(
                                    "Segment",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=SEGMENT_DROPDOWN_ID,
                                        toggle_id=SEGMENT_TOGGLE_ID,
                                        menu_id=SEGMENT_MENU_ID,
                                        filter_key=SEGMENT_FILTER_KEY,
                                        options=_dropdown_options(segment_options),
                                        value="All",
                                    ),
                                ),
                                _build_filter(
                                    "Specific Models",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=MODEL_DROPDOWN_ID,
                                        toggle_id=MODEL_TOGGLE_ID,
                                        menu_id=MODEL_MENU_ID,
                                        filter_key=MODEL_FILTER_KEY,
                                        options=model_select_options,
                                        value="all",
                                    ),
                                ),
                            ],
                        ),
                        html.Div(style={"marginTop": "12px"}, children=[_build_loss_subnav()]),
                    ],
                ),
            ],
        ),
        html.Div(
            className="content",
            children=[
                html.Div(
                    className="tab-panel active pd-performance-app",
                    children=html.Div(
                        id=CONTENT_ID,
                        children=render_loss_performance_content(data, default_model, "All", default_monitoring_point, {}),
                    ),
                ),
            ],
        ),
    ]
