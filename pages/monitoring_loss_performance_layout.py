"""Layout for the Loss Performance page."""

from __future__ import annotations

from dash import dcc, html

from ..components.charts import build_loss_metric_trend_figure, build_loss_rag_trend_figure
from ..components.filters import build_chart_header
from ..components.kpis import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)
from ..data.loss import (
    build_loss_period_summary,
    build_loss_rag_trend,
    get_loss_default_model,
    get_loss_model_options,
    get_loss_monitoring_point_options,
    get_loss_segments_for_model,
    get_loss_thresholds,
)
from ..data.transformations import format_pd_compact_amount, pd_tone_class
from .monitoring_lgd_performance_layout import (
    _build_chart_panel,
    _build_filter,
    _dropdown_options,
    _flow_connector_spans,
    _flow_metric,
    _flow_stage,
    _subnav_link,
)

CONTENT_ID = "loss-dashboard-content"
MODEL_DROPDOWN_ID = "loss-model-dropdown"
SEGMENT_DROPDOWN_ID = "loss-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "loss-monitoring-point-dropdown"
LOSS_SUBNAV_ID = "loss-subnav"
RANGE_STORE_ID = "loss-range-store"
PERFORMANCE_RAG_RANGE_KEY = "loss_performance_rag"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


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
    return html.Div(
        className="pd-overview-flow-wrap",
        children=html.Div(
            className="lgd-overview-flow loss-overview-flow",
            children=[
                html.Div(_flow_stage("1. Component"), className="loss-flow-stage-input"),
                html.Div(_flow_stage("2. Test"), className="loss-flow-stage-tests"),
                html.Div(_flow_stage("3. Performance RAG"), className="loss-flow-stage-performance"),
                html.Div(
                    className="pd-overview-flow-input lgd-flow-input loss-flow-input",
                    children=[html.Strong("Loss"), html.Span("1 year monitoring")],
                ),
                html.Div(
                    className="pd-overview-flow-test-stack loss-flow-tests",
                    children=[
                        *_flow_connector_spans(incoming=True, outgoing=True),
                        _flow_metric(
                            "ME % 1 year",
                            summary["current"].get("ME %"),
                            "ME",
                            summary["metric_rags"].get("ME %", "N/A"),
                            "#loss-performance",
                            previous_value=summary["previous"].get("ME %"),
                            previous_period=summary["previous_monitoring_point"],
                        ),
                    ],
                ),
                html.Div(
                    className=f"pd-overview-flow-performance pd-overview-flow-performance-{pd_tone_class(summary['performance_rag'])} loss-flow-performance",
                    children=[
                        html.Span("Performance RAG", className="pd-overview-flow-performance-title"),
                        html.Strong([pd_rag_dot(summary["performance_rag"]), f" {summary['performance_rag']}"]),
                    ],
                ),
            ],
            **{"aria-label": "Loss monitoring overview process flow"},
        ),
    )


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
        build_pd_test_card(
            "ME %",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {
                "format": "percent",
                "card_title": "ME % 1 year",
                "extra_meta_rows": [
                    {"label": "Mean Error", "value": _money(current.get("ME"))},
                    {"label": "Predicted Loss", "value": _money(current.get("Predicted Loss"))},
                    {"label": "Actual Loss", "value": _money(current.get("Actual Loss"))},
                ],
            },
        ),
        build_pd_section_rag_card(
            "Performance RAG",
            summary["performance_rag"],
            summary["previous_performance_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
    ]

    chapter_1 = html.Section(
        id="loss-rag-assignment",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "1.",
                "RAG Assignment",
                "Core monitoring view for Loss model health, where ME % feeds directly into the Performance RAG.",
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
                "RAG Assignment Overview",
                "At-a-glance summary of the 1 year Loss monitoring flow from ME % to Performance RAG.",
                summary["performance_rag"],
                {"status_label": "Performance RAG"},
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
                "Assess predicted loss against the observed loss proxy using ME %.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-discrimination-test-grid", children=performance_cards),
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
            _build_chart_panel(
                "ME % Trend",
                "Mean error percentage by monitoring point with Loss threshold shading.",
                build_loss_metric_trend_figure(metric_rows, data["monitoring_thresholds"], monitoring_point),
            ),
        ],
    )

    return [
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, performance_section]),
    ]


def page_layout(data: dict) -> list:
    """Build the Loss page with top controls and live content."""
    model_options = get_loss_model_options(data)
    default_model = model_options[0] if model_options else get_loss_default_model(data)
    segment_options = get_loss_segments_for_model(data, default_model)
    monitoring_options = get_loss_monitoring_point_options(data, default_model, "All")
    default_monitoring_point = monitoring_options[1] if monitoring_options[:1] == ["Latest"] and len(monitoring_options) > 1 else (monitoring_options[0] if monitoring_options else "")

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        html.Div(
            className="top-bar lgd-top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("Wholesale Portfolio Model Monitoring Dashboard", className="monitoring-dashboard-title"),
                        html.Div(
                            className="monitoring-controls lgd-header-controls",
                            children=[
                                _build_filter(
                                    "Monitoring Point",
                                    dcc.Dropdown(
                                        id=MONITORING_POINT_DROPDOWN_ID,
                                        options=_dropdown_options(monitoring_options),
                                        value=default_monitoring_point,
                                        clearable=False,
                                        className="monitoring-top-select monitoring-point-select lgd-header-select",
                                    ),
                                ),
                                _build_filter(
                                    "Segment",
                                    dcc.Dropdown(
                                        id=SEGMENT_DROPDOWN_ID,
                                        options=_dropdown_options(segment_options),
                                        value="All",
                                        clearable=False,
                                        className="monitoring-top-select lgd-header-select",
                                    ),
                                ),
                                _build_filter(
                                    "Specific Models",
                                    dcc.Dropdown(
                                        id=MODEL_DROPDOWN_ID,
                                        options=_dropdown_options(model_options),
                                        value=default_model,
                                        clearable=False,
                                        className="monitoring-top-select lgd-header-select",
                                    ),
                                ),
                                _build_loss_subnav(),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="content",
            children=[
                html.Div(
                    className="pd-performance-app lgd-performance-app loss-performance-app",
                    children=html.Div(
                        id=CONTENT_ID,
                        children=render_loss_performance_content(data, default_model, "All", default_monitoring_point, {}),
                    ),
                ),
            ],
        ),
    ]
