"""Layout for the EAD Performance page."""

from __future__ import annotations

from dash import dcc, html

from ..components.charts import (
    build_ead_calibration_rag_trend_figure,
    build_ead_discrimination_rag_trend_figure,
    build_ead_metric_trend_figure,
)
from ..components.filters import build_chart_header
from ..components.kpis import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)
from ..data.ead import (
    EAD_CALIBRATION_METRICS,
    build_ead_calibration_rag_trend,
    build_ead_discrimination_rag_trend,
    build_ead_period_summary,
    get_ead_default_model,
    get_ead_model_options,
    get_ead_monitoring_point_options,
    get_ead_segments_for_model,
    get_ead_thresholds,
)
from ..data.transformations import pd_tone_class
from .monitoring_lgd_performance_layout import (
    _build_chart_panel,
    _build_filter,
    _dropdown_options,
    _flow_connector_spans,
    _flow_metric,
    _flow_rag,
    _flow_stage,
    _subnav_link,
)

CONTENT_ID = "ead-dashboard-content"
MODEL_DROPDOWN_ID = "ead-model-dropdown"
SEGMENT_DROPDOWN_ID = "ead-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "ead-monitoring-point-dropdown"
EAD_SUBNAV_ID = "ead-subnav"
RANGE_STORE_ID = "ead-range-store"
CALIBRATION_RAG_RANGE_KEY = "ead_calibration_rag"
DISCRIMINATION_RAG_RANGE_KEY = "ead_discrimination_rag"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _build_ead_subnav() -> html.Div:
    return html.Div(
        id=EAD_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("ead-overview", "Overview", active=True),
                            _subnav_link("ead-calibration", "Calibration Conservatism"),
                            _subnav_link("ead-discrimination", "Discriminatory Power"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group monitoring-section-subnav-group-secondary pd-subnav-group",
                children=[
                    html.Div("Post Subjective Review Analysis", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("ead-mev-scenario", "MEV Range and Scenario Tests"),
                            _subnav_link("ead-post-subjective-review", "Post Subjective Review"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_ead_overview_flow(summary: dict) -> html.Div:
    return html.Div(
        className="pd-overview-flow-wrap",
        children=html.Div(
            className="lgd-overview-flow",
            children=[
                html.Div(_flow_stage("1. Component"), className="lgd-flow-stage-input"),
                html.Div(_flow_stage("2. Tests"), className="lgd-flow-stage-tests"),
                html.Div(_flow_stage("3. Monitoring Dimension RAG"), className="lgd-flow-stage-dimension"),
                html.Div(_flow_stage("4. Performance RAG"), className="lgd-flow-stage-performance"),
                html.Div(
                    className="pd-overview-flow-input lgd-flow-input",
                    children=[html.Strong("EAD"), html.Span("1 year monitoring")],
                ),
                html.Div(
                    className="pd-overview-flow-test-stack lgd-flow-tests-calibration",
                    children=[
                        *_flow_connector_spans(incoming=True, outgoing=True),
                        _flow_metric(
                            "ME 1 year",
                            summary["current"].get("ME"),
                            "ME",
                            summary["metric_rags"].get("ME", "N/A"),
                            "#ead-calibration",
                            previous_value=summary["previous"].get("ME"),
                            previous_period=summary["previous_monitoring_point"],
                        ),
                        _flow_metric(
                            "RMSE 1 year",
                            summary["current"].get("RMSE"),
                            "RMSE",
                            summary["metric_rags"].get("RMSE", "N/A"),
                            "#ead-calibration",
                            previous_value=summary["previous"].get("RMSE"),
                            previous_period=summary["previous_monitoring_point"],
                        ),
                    ],
                ),
                html.Div(
                    className="pd-overview-flow-test-stack lgd-flow-tests-discrimination",
                    children=[
                        *_flow_connector_spans(incoming=True, outgoing=True),
                        _flow_metric(
                            "Kendall's Tau 1 year",
                            summary["current"].get("Kendall's Tau"),
                            "Kendall's Tau",
                            summary["metric_rags"].get("Kendall's Tau", "N/A"),
                            "#ead-discrimination",
                            previous_value=summary["previous"].get("Kendall's Tau"),
                            previous_period=summary["previous_monitoring_point"],
                        ),
                    ],
                ),
                html.Div(
                    _flow_rag("Calibration Conservatism RAG", summary["calibration_rag"], "#ead-calibration", incoming=True, outgoing=True),
                    className="lgd-flow-dimension-calibration",
                ),
                html.Div(
                    _flow_rag("Discriminatory Power RAG", summary["discrimination_rag"], "#ead-discrimination", incoming=True, outgoing=True),
                    className="lgd-flow-dimension-discrimination",
                ),
                html.Div(
                    className=f"pd-overview-flow-performance pd-overview-flow-performance-{pd_tone_class(summary['performance_rag'])} lgd-flow-performance",
                    children=[
                        html.Span("Performance RAG", className="pd-overview-flow-performance-title"),
                        html.Strong([pd_rag_dot(summary["performance_rag"]), f" {summary['performance_rag']}"]),
                    ],
                ),
            ],
            **{"aria-label": "EAD monitoring overview process flow"},
        ),
    )


def render_ead_performance_content(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
    range_store: dict | None = None,
) -> list:
    range_store = range_store or {}
    summary = build_ead_period_summary(data, selected_model, selected_segment, selected_monitoring_point)
    thresholds = get_ead_thresholds(data)
    context = {
        "snapshot_quarter": summary["monitoring_point"] or "No monitoring point",
        "previous_quarter": summary["previous_monitoring_point"],
    }

    if not summary["current"]:
        return [
            html.Div(
                className="section-card pd-placeholder-card",
                children=[
                    html.Div("No EAD data", className="pd-placeholder-badge"),
                    html.Div("EAD Performance", className="pd-placeholder-title"),
                    html.P("No EAD observations are available for the selected model and segment."),
                ],
            )
        ]

    calibration_cards = [
        build_pd_test_card(
            metric,
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {"format": "percent", "card_title": f"{metric} 1 year"},
        )
        for metric in EAD_CALIBRATION_METRICS
    ]
    calibration_cards.append(
        build_pd_section_rag_card(
            "Calibration Conservatism RAG",
            summary["calibration_rag"],
            summary["previous_calibration_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        )
    )
    discrimination_cards = [
        build_pd_test_card(
            "Kendall's Tau",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {"format": "ratio", "card_title": "Kendall's Tau 1 year"},
        ),
        build_pd_section_rag_card(
            "Discriminatory Power RAG",
            summary["discrimination_rag"],
            summary["previous_discrimination_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
    ]

    metric_rows = summary["metric_rows"]
    monitoring_point = summary["monitoring_point"]
    calibration_rag_trend = build_ead_calibration_rag_trend(data, metric_rows)
    calibration_rag_periods = [row["quarter"] for row in calibration_rag_trend]
    discrimination_rag_trend = build_ead_discrimination_rag_trend(data, metric_rows)
    discrimination_rag_periods = [row["quarter"] for row in discrimination_rag_trend]

    chapter_1 = html.Section(
        id="ead-rag-assignment",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "1.",
                "RAG Assignment",
                "Core monitoring view for EAD model health, combining the current overview with calibration "
                "conservatism and discriminatory-power diagnostics.",
                options={"note": f"Monitoring point {monitoring_point}"},
            ),
        ],
    )

    overview_section = html.Section(
        id="ead-overview",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Overview",
                "EAD RAG Assignment Overview",
                "At-a-glance summary of the 1 year EAD monitoring flow from metric tests to dimension RAGs and Performance RAG.",
                summary["performance_rag"],
                {"status_label": "Performance RAG"},
            ),
            _build_ead_overview_flow(summary),
        ],
    )

    calibration_section = html.Section(
        id="ead-calibration",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 Calibration Conservatism",
                "Calibration Conservatism",
                "Compare realized EAD against predicted EAD using mean error and RMSE.",
                summary["calibration_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-calibration-test-grid", children=calibration_cards),
            html.Div(
                id="ead-calibration-rag-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Calibration Conservatism RAG Trend",
                        "Quarter-by-quarter Calibration Conservatism RAG shown as a simple color-coded dot timeline.",
                        CALIBRATION_RAG_RANGE_KEY,
                        calibration_rag_periods,
                        range_store.get(CALIBRATION_RAG_RANGE_KEY),
                    ),
                    dcc.Graph(
                        id="ead-calibration-rag-trend-chart",
                        figure=build_ead_calibration_rag_trend_figure(
                            calibration_rag_trend,
                            monitoring_point,
                            range_store.get(CALIBRATION_RAG_RANGE_KEY),
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                    ),
                ],
            ),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
                    _build_chart_panel("ME Trend", "Mean error by monitoring point with EAD threshold shading.", build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "ME", monitoring_point)),
                    _build_chart_panel("RMSE Trend", "Root mean squared error by monitoring point with EAD threshold shading.", build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "RMSE", monitoring_point)),
                ],
            ),
        ],
    )

    discrimination_section = html.Section(
        id="ead-discrimination",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.3 Discriminatory Power",
                "Discriminatory Power",
                "Assess whether higher predicted EAD observations rank consistently with higher realized EAD outcomes.",
                summary["discrimination_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-discrimination-test-grid", children=discrimination_cards),
            html.Div(
                id="ead-discrimination-rag-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Discriminatory Power RAG Trend",
                        "Quarter-by-quarter Discriminatory Power RAG shown as a simple color-coded dot timeline.",
                        DISCRIMINATION_RAG_RANGE_KEY,
                        discrimination_rag_periods,
                        range_store.get(DISCRIMINATION_RAG_RANGE_KEY),
                    ),
                    dcc.Graph(
                        id="ead-discrimination-rag-trend-chart",
                        figure=build_ead_discrimination_rag_trend_figure(
                            discrimination_rag_trend,
                            monitoring_point,
                            range_store.get(DISCRIMINATION_RAG_RANGE_KEY),
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                    ),
                ],
            ),
            _build_chart_panel(
                "Kendall's Tau Trend",
                "Rank-ordering strength by monitoring point with EAD threshold shading.",
                build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "Kendall's Tau", monitoring_point),
            ),
        ],
    )

    chapter_2 = html.Section(
        id="ead-post-subjective-review-analysis",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "2.",
                "Post Subjective Review Analysis",
                "Qualitative review and scenario context represented using dashboard1's current EAD source data availability.",
            ),
        ],
    )

    mev_section = html.Section(
        id="ead-mev-scenario",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 MEV Range and Scenario Tests",
                "MEV Range and Scenario Tests",
                "Dashboard2 review sections are represented here using dashboard1's current source data availability.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            html.Div(
                className="pd-test-grid pd-discrimination-test-grid",
                children=[
                    html.Article(
                        className=f"pd-test-card pd-test-{pd_tone_class(summary['performance_rag'])}",
                        children=[
                            html.Div(className="pd-test-card-heading", children=[html.Div([html.Div([html.H4("MEV Range Analysis")], className="pd-card-title-row")])]),
                            html.Div("Reference", className="pd-test-value"),
                            html.Div("No EAD MEV catalog is configured in dashboard1 source data.", className="pd-test-meta"),
                        ],
                    ),
                    html.Article(
                        className=f"pd-test-card pd-test-{pd_tone_class(summary['performance_rag'])}",
                        children=[
                            html.Div(className="pd-test-card-heading", children=[html.Div([html.Div([html.H4("Scenario Tests")], className="pd-card-title-row")])]),
                            html.Div("Reference", className="pd-test-value"),
                            html.Div("No EAD scenario test feed is configured in dashboard1 source data.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
        ],
    )

    post_review_section = html.Section(
        id="ead-post-subjective-review",
        className="pd-content-section pd-placeholder-section",
        children=[
            build_pd_section_heading(
                "2.2 Post Subjective Review",
                "Post Subjective Review",
                "Future landing area for the post subjective review analysis package.",
                "N/A",
                {"show_rag": False},
            ),
            html.Div(
                className="section-card pd-placeholder-card",
                children=[
                    html.P(
                        "This placeholder section is ready for the future summary narrative, key flags, and "
                        "cross-check metrics that will frame the post subjective review analysis."
                    ),
                ],
            ),
        ],
    )

    return [
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, calibration_section, discrimination_section]),
        chapter_2,
        html.Div(className="pd-chapter-body pd-chapter-body-secondary", children=[mev_section, post_review_section]),
    ]


def page_layout(data: dict) -> list:
    """Build the EAD page with top controls and live content."""
    model_options = get_ead_model_options(data)
    default_model = model_options[0] if model_options else get_ead_default_model(data)
    segment_options = get_ead_segments_for_model(data, default_model)
    monitoring_options = get_ead_monitoring_point_options(data, default_model, "All")
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
                                _build_ead_subnav(),
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
                    className="pd-performance-app lgd-performance-app ead-performance-app",
                    children=html.Div(
                        id=CONTENT_ID,
                        children=render_ead_performance_content(data, default_model, "All", default_monitoring_point, {}),
                    ),
                ),
            ],
        ),
    ]
