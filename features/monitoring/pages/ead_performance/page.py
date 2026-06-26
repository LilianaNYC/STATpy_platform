"""Layout for the EAD Performance page.

Ports ``monitoring_ead_performance_layout.py`` from the integrated branch,
adapting imports to the ``features/monitoring/pages/`` package structure used
on ``main``.
"""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from .....components.charts import (
    build_ead_calibration_rag_trend_figure,
    build_ead_discrimination_rag_trend_figure,
    build_ead_metric_trend_figure,
)
from .....components import filters as shared_filters
from .....components.filters import build_chart_header
from .....data.analytics.calculations import (
    fmt_n,
    format_pd_metric,
    pd_tone_class,
)
from .....data.analytics.ead import (
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
from ...data_access import PD_PERFORMANCE_DATA
from ..pd_performance.cards import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)

CONTENT_ID = "ead-dashboard-content"
REPORTING_CYCLE_ID = "ead-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "ead-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "ead-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "ead-reporting-cycle"
MODEL_DROPDOWN_ID = "ead-model-dropdown"
SEGMENT_DROPDOWN_ID = "ead-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "ead-monitoring-point-dropdown"
MODEL_TOGGLE_ID = "ead-model-toggle"
MODEL_MENU_ID = "ead-model-menu"
MODEL_SELECT_ALL_ID = "ead-model-select-all"
SEGMENT_TOGGLE_ID = "ead-segment-toggle"
SEGMENT_MENU_ID = "ead-segment-menu"
MONITORING_POINT_TOGGLE_ID = "ead-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "ead-monitoring-point-menu"
MODEL_FILTER_KEY = "ead-model"
SEGMENT_FILTER_KEY = "ead-segment"
MONITORING_POINT_FILTER_KEY = "ead-monitoring-point"
EAD_SUBNAV_ID = "ead-subnav"
RANGE_STORE_ID = "ead-range-store"
CALIBRATION_RAG_RANGE_KEY = "ead_calibration_rag"
DISCRIMINATION_RAG_RANGE_KEY = "ead_discrimination_rag"
ME_RANGE_KEY = "ead_me"
RMSE_RANGE_KEY = "ead_rmse"
KENDALL_RANGE_KEY = "ead_kendall"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------------------------------------------------------------------------
# Shared layout helpers (duplicated from LGD layout until LGD is ported)
# ---------------------------------------------------------------------------


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


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


def _build_filter(label: str, component) -> html.Div:
    return html.Div(className="monitoring-filter", children=[html.Label(label), component])


def _subnav_link(section_id: str, label: str, active: bool = False) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


def _flow_connector_spans(*, incoming: bool = False, outgoing: bool = False) -> list[html.Span]:
    spans: list[html.Span] = []
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


def _flow_rag(
    label: str,
    rag: str,
    href: str,
    note: str | None = None,
    *,
    incoming: bool = False,
    outgoing: bool = False,
) -> html.Article:
    children = [
        *_flow_connector_spans(incoming=incoming, outgoing=outgoing),
        html.Span(label, className="pd-overview-flow-node-label"),
        html.Span([pd_rag_dot(rag), f" {rag}"], className="pd-overview-flow-node-value pd-overview-flow-node-value-rag"),
    ]
    if note:
        children.append(html.Span(note, className="pd-overview-flow-node-note lgd-cascade-note"))
    return html.Article(
        className=f"pd-overview-flow-node pd-overview-flow-node-{pd_tone_class(rag)}",
        children=html.A(
            className="pd-overview-flow-link",
            href=href,
            children=children,
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
# Sub-nav
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Overview flow diagram
# ---------------------------------------------------------------------------


def _build_ead_overview_flow(summary: dict) -> html.Div:
    from .....components.kpis import (
        build_pd_overview_flow_input,
        build_pd_overview_flow_metric,
        build_pd_overview_flow_stage,
        build_pd_overview_flow_test_stack,
    )

    me_rag = summary["metric_rags"].get("ME", "N/A")
    rmse_rag = summary["metric_rags"].get("RMSE", "N/A")
    tau_rag = summary["metric_rags"].get("Kendall's Tau", "N/A")
    calibration_rag = summary["calibration_rag"]
    discrimination_rag = summary["discrimination_rag"]
    performance_rag = summary["performance_rag"]

    flow_children = [
        html.Div(build_pd_overview_flow_stage("1.", "Component"), className="lgd-flow-stage-input"),
        html.Div(build_pd_overview_flow_stage("2.", "Tests"), className="lgd-flow-stage-tests"),
        html.Div(build_pd_overview_flow_stage("3.", "Monitoring Dimension RAG"), className="lgd-flow-stage-dimension"),
        html.Div(build_pd_overview_flow_stage("4.", "Performance RAG"), className="lgd-flow-stage-performance"),

        html.Div(
            build_pd_overview_flow_input("EAD", {"note": "1 year monitoring"}),
            className="lgd-flow-input",
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric(
                    "Mean Error 1 year", summary["current"].get("ME"), "percent", me_rag,
                    {"href": "#ead-calibration"},
                ),
                build_pd_overview_flow_metric(
                    "RMSE 1 year", summary["current"].get("RMSE"), "percent", rmse_rag,
                    {"href": "#ead-calibration"},
                ),
            ],
            {"incoming": True, "extra_class": "lgd-flow-tests-calibration"},
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric(
                    "Kendall's Tau 1 year", summary["current"].get("Kendall's Tau"), "ratio", tau_rag,
                    {"href": "#ead-discrimination"},
                ),
            ],
            {"incoming": True, "extra_class": "lgd-flow-tests-discrimination"},
        ),

        build_pd_overview_flow_metric(
            "Calibration Conservatism RAG", calibration_rag, "rag", calibration_rag,
            {
                "is_rag": True,
                "href": "#ead-calibration",
                "incoming": True,
                "outgoing": True,
                "extra_class": "lgd-flow-dimension-calibration",
            },
        ),

        build_pd_overview_flow_metric(
            "Discriminatory Power RAG", discrimination_rag, "rag", discrimination_rag,
            {
                "is_rag": True,
                "href": "#ead-discrimination",
                "incoming": True,
                "outgoing": True,
                "extra_class": "lgd-flow-dimension-discrimination",
            },
        ),

        html.Div(
            className="lgd-flow-performance",
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
            className="lgd-overview-flow",
            **{"aria-label": "EAD monitoring overview process flow"},
        ),
    )


# ---------------------------------------------------------------------------
# Content renderer (called on every filter change)
# ---------------------------------------------------------------------------


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
        build_pd_section_rag_card(
            "Calibration Conservatism RAG",
            summary["calibration_rag"],
            summary["previous_calibration_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
        build_pd_test_card(
            "RMSE",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {"format": "percent", "card_title": "RMSE 1 year"},
        ),
        build_pd_test_card(
            "ME",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {"format": "percent", "card_title": "Mean Error 1 year"},
        ),
    ]
    discrimination_cards = [
        build_pd_section_rag_card(
            "Discriminatory Power RAG",
            summary["discrimination_rag"],
            summary["previous_discrimination_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
        build_pd_test_card(
            "Kendall's Tau",
            summary["current"],
            summary["previous"],
            thresholds,
            context,
            {"format": "ratio", "card_title": "Kendall's Tau 1 year"},
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
                {"show_rag": False},
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
            html.Div(className="pd-test-grid pd-test-grid-3", children=calibration_cards),
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
                    html.Div(
                        id="ead-me-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Mean Error Trend",
                                "Mean error by monitoring point with EAD threshold shading.",
                                ME_RANGE_KEY,
                                calibration_rag_periods,
                                range_store.get(ME_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="ead-me-trend-chart",
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "ME", monitoring_point),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                    html.Div(
                        id="ead-rmse-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "RMSE Trend",
                                "Root mean squared error by monitoring point with EAD threshold shading.",
                                RMSE_RANGE_KEY,
                                calibration_rag_periods,
                                range_store.get(RMSE_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="ead-rmse-trend-chart",
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "RMSE", monitoring_point),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
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
            html.Div(className="pd-test-grid", style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"}, children=discrimination_cards),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
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
                    html.Div(
                        id="ead-kendall-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Kendall's Tau Trend",
                                "Rank-ordering strength by monitoring point with EAD threshold shading.",
                                KENDALL_RANGE_KEY,
                                discrimination_rag_periods,
                                range_store.get(KENDALL_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="ead-kendall-trend-chart",
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "Kendall's Tau", monitoring_point),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                ],
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


# ---------------------------------------------------------------------------
# Top-level page builder
# ---------------------------------------------------------------------------


def page_layout() -> list:
    """Build the EAD page with top controls and live content."""
    from .....data.monitoring.filters_config import load_filter_config, model_names, segment_values
    from .....data.analytics.ead import set_ead_metrics
    data = PD_PERFORMANCE_DATA
    cfg = load_filter_config()
    model_options = model_names("ead")
    default_model = "all"
    segment_options = ["All", *segment_values()]
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    cycle_data = (data.get("ead_observations_by_cycle") or {}).get(default_cycle)
    if cycle_data:
        set_ead_metrics(cycle_data.get("metrics_store"), cycle_data.get("quarters"))
    else:
        set_ead_metrics(None, [])
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_options = cycle_quarters if cycle_quarters else get_ead_monitoring_point_options(data, None, "All")
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
                        html.Div(style={"marginTop": "12px"}, children=[_build_ead_subnav()]),
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
                        children=render_ead_performance_content(data, default_model, "All", default_monitoring_point, {}),
                    ),
                ),
            ],
        ),
    ]
