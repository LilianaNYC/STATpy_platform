"""Layout for the Loss Performance page."""

from __future__ import annotations

from dash import dcc, html

from .....shared.ui.charts import build_loss_metric_trend_figure
from .....shared.ui import controls as shared_filters
from .....shared.ui.controls import build_chart_header, build_section_filter_bar, build_section_filter_item
from .....shared.domain.calculations import format_pd_compact_amount, pd_tone_class
from .....shared.theme import normalize_theme_value
from ...domain.loss import (
    build_loss_period_summary,
    get_loss_monitoring_point_options,
    get_loss_thresholds,
)
from .cards import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)
from .post_subjective import build_executive_summary

CONTENT_ID = "loss-dashboard-content"
APPLY_FILTERS_ID = "loss-apply-filters"
APPLIED_FILTERS_STORE_ID = "loss-applied-filters-store"
REPORTING_CYCLE_ID = "loss-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "loss-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "loss-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "loss-reporting-cycle"
MODEL_DROPDOWN_ID = "loss-model-dropdown"
SEGMENT_DROPDOWN_ID = "loss-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "loss-monitoring-point-dropdown"
MODEL_TOGGLE_ID = "loss-model-toggle"
MODEL_MENU_ID = "loss-model-menu"
SEGMENT_TOGGLE_ID = "loss-segment-toggle"
SEGMENT_MENU_ID = "loss-segment-menu"
MONITORING_POINT_TOGGLE_ID = "loss-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "loss-monitoring-point-menu"
MODEL_FILTER_KEY = "loss-model"
SEGMENT_FILTER_KEY = "loss-segment"
MONITORING_POINT_FILTER_KEY = "loss-monitoring-point"
LOSS_SUBNAV_ID = "loss-subnav"
RANGE_STORE_ID = "loss-range-store"
PERFORMANCE_SECTION_RANGE_KEY = "loss_performance_section"

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
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-rag active",
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
    from .cards import (
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
    theme_value: str | None = None,
) -> list:
    theme = normalize_theme_value(theme_value)
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
    periods = [row["Monitoring Period"] for row in metric_rows]

    performance_cards = [
        build_pd_section_rag_card(
            "Performance RAG",
            summary["performance_rag"],
            summary["previous_performance_rag"],
            context,
            {
                "hide_status": True,
                "hide_comparison": True,
                "meta_label": "Monitoring point",
                "extra_meta_rows": [
                    {"label": "Predicted Loss", "value": _money(current.get("Predicted Loss"))},
                    {"label": "Actual Loss", "value": _money(current.get("Actual Loss"))},
                ],
            },
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
                "Core monitoring view for Loss model health, combining the current overview with mean error diagnostics and the resulting Performance RAG.",
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
                "At-a-glance summary of the 1-year Loss monitoring flow from Mean Error % to Performance RAG.",
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
                "Compares predicted loss against the observed loss proxy using Mean Error % across the monitored 1-year population.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid loss-performance-test-grid", children=performance_cards),
            build_section_filter_bar([
                build_section_filter_item(
                    "Display filters",
                    range_key=PERFORMANCE_SECTION_RANGE_KEY,
                    periods=periods,
                    range_value=range_store.get(PERFORMANCE_SECTION_RANGE_KEY),
                ),
            ]),
            html.Div(
                id="loss-me-pct-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Mean Error % Trend",
                        "Mean error percentage by monitoring point, with Loss threshold shading.",
                    ),
                    dcc.Graph(
                        id="loss-me-pct-trend-chart",
                        figure=build_loss_metric_trend_figure(
                            metric_rows,
                            data["monitoring_thresholds"],
                            monitoring_point,
                            range_store.get(PERFORMANCE_SECTION_RANGE_KEY),
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                    ),
                ],
            ),
            html.Div(
                id="loss-component-me-pct-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Component Mean Error % Trend",
                        "Mean error percentage by monitoring point for Net Charge-Offs (NCO) and Allowance for Credit Losses (ACL).",
                    ),
                    html.Div(
                        className="pd-trend-detail-grid loss-component-trend-grid",
                        children=[
                            html.Div(
                                className="loss-component-trend-block",
                                children=[
                                    build_chart_header(
                                        "NCO Mean Error % Trend",
                                        "Net Charge-Off mean error percentage by monitoring point.",
                                    ),
                                    dcc.Graph(
                                        id="loss-nco-me-pct-trend-chart",
                                        figure=build_loss_metric_trend_figure(
                                            metric_rows,
                                            data["monitoring_thresholds"],
                                            monitoring_point,
                                            range_store.get(PERFORMANCE_SECTION_RANGE_KEY),
                                            metric="NCO ME %",
                                            value_label="NCO Mean Error",
                                        ),
                                        config=_GRAPH_CONFIG,
                                        className="loss-component-trend-chart",
                                        style={"height": "308px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                className="loss-component-trend-block",
                                children=[
                                    build_chart_header(
                                        "ACL Mean Error % Trend",
                                        "Allowance for Credit Losses mean error percentage by monitoring point.",
                                    ),
                                    dcc.Graph(
                                        id="loss-acl-me-pct-trend-chart",
                                        figure=build_loss_metric_trend_figure(
                                            metric_rows,
                                            data["monitoring_thresholds"],
                                            monitoring_point,
                                            range_store.get(PERFORMANCE_SECTION_RANGE_KEY),
                                            metric="ACL ME %",
                                            value_label="ACL Mean Error",
                                        ),
                                        config=_GRAPH_CONFIG,
                                        className="loss-component-trend-chart",
                                        style={"height": "308px"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    executive_summary = build_executive_summary(
        "The Loss Performance dashboard is the monitoring view for the Loss model, which combines PD, LGD, and "
        "EAD to estimate portfolio-level credit losses. It tracks Mean Error % — the gap between predicted and "
        "actual loss — against the agreed RAG thresholds, and breaks that comparison out by Net Charge-Offs (NCO) "
        "and the Allowance for Credit Losses (ACL) so reviewers can judge whether the loss estimate remains "
        "defensible across model use case / cycles.",
        theme,
    )

    return [
        executive_summary,
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, performance_section]),
    ]


def _build_loss_apply_button() -> html.Div:
    return html.Div(
        className="monitoring-filter saas-top-filter-action",
        children=[
            html.Div(
                className="pd-mev-filter-actions",
                children=[
                    html.Button(
                        "Apply filters",
                        id=APPLY_FILTERS_ID,
                        className="btn pd-mev-filter-reset saas-top-filter-reset saas-top-filter-apply",
                        n_clicks=0,
                        type="button",
                        title="Load the dashboard using the selected filters.",
                    ),
                ],
            ),
        ],
    )


def build_loss_apply_prompt() -> html.Section:
    return html.Section(
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    "The Loss Performance dashboard is the monitoring view for the Loss model, which combines PD, "
                    "LGD, and EAD to estimate portfolio-level credit losses. It tracks Mean Error % — the gap "
                    "between predicted and actual loss — against the agreed RAG thresholds, and breaks that "
                    "comparison out by Net Charge-Offs (NCO) and the Allowance for Credit Losses (ACL) so "
                    "reviewers can judge whether the loss estimate remains defensible across model use case / cycles.",
                ],
            ),
            html.Div(
                className="saas-model-panel-stack",
                children=[
                    html.Div(
                        className="section-card pd-mev-empty-state saas-getting-started",
                        children=[
                            html.Div("Getting started with the Loss Performance dashboard", className="pd-mev-chart-title"),
                            html.P(
                                "Set your filters in the top bar, then click “Apply filters” to render the dashboard. "
                                "Use the quick guide below to move from setup to analysis smoothly.",
                                className="pd-section-subtitle",
                            ),
                            html.Div(
                                className="saas-getting-started-summary",
                                children=[
                                    html.Div("Quick start", className="saas-getting-started-summary-title"),
                                    html.Div(
                                        className="saas-getting-started-highlights",
                                        children=[
                                            html.Span("1. Choose Model Use Case / Cycle and Monitoring Point.", className="saas-getting-started-highlight"),
                                            html.Span("2. Pick a Segment or a Specific Model — not both.", className="saas-getting-started-highlight"),
                                            html.Span("3. Click Apply filters to load the dashboard.", className="saas-getting-started-highlight"),
                                        ],
                                    ),
                                    html.Div(
                                        "The dashboard always reflects the most recent applied filter snapshot, not any unapplied edits still sitting in the top bar.",
                                        className="saas-getting-started-summary-note",
                                    ),
                                ],
                            ),
                            html.Ol(
                                className="saas-getting-started-steps",
                                children=[
                                    html.Li([
                                        html.Strong("Pick a Model Use Case / Cycle. "),
                                        "Choose the cycle to review (e.g. CCAR 2026). This sets which monitoring points and "
                                        "precomputed metrics are available.",
                                    ]),
                                    html.Li([
                                        html.Strong("Set the Monitoring Point. "),
                                        "Pick the as-of quarter for the snapshot. The available quarters follow the selected "
                                        "model use case / cycle, and trends are shown up to this point.",
                                    ]),
                                    html.Li([
                                        html.Strong("Choose your population. "),
                                        "Select a Segment or a single Specific Model — these two filters are mutually "
                                        "exclusive. Leaving both at “All” reads the portfolio-level (All Models) metrics.",
                                    ]),
                                    html.Li([
                                        html.Strong("Click “Apply filters”. "),
                                        "The dashboard loads here. Nothing renders until you apply, so this starting guide "
                                        "stays visible until the first Apply.",
                                    ]),
                                    html.Li([
                                        html.Strong("Read the analysis. "),
                                        "Once loaded, the dashboard is organised as:",
                                        html.Ul(
                                            className="saas-getting-started-substeps",
                                            children=[
                                                html.Li([
                                                    html.Strong("1.1 Overview — "),
                                                    "a process-flow summary from Mean Error % to the Performance RAG.",
                                                ]),
                                                html.Li([
                                                    html.Strong("1.2 Performance — "),
                                                    "Performance RAG and Mean Error % test cards, an overall Mean Error % "
                                                    "trend, and a by-component trend for Net Charge-Offs (NCO) and the "
                                                    "Allowance for Credit Losses (ACL).",
                                                ]),
                                            ],
                                        ),
                                    ]),
                                    html.Li([
                                        html.Strong("Fine-tune within each section. "),
                                        "The trend charts have Window / From / To range controls for on-screen analysis — "
                                        "these do not require re-applying the top filters.",
                                    ]),
                                    html.Li([
                                        html.Strong("Start over. "),
                                        "Refresh the page at any time to clear the dashboard and return to this starting view.",
                                    ]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Top-level page layout
# ---------------------------------------------------------------------------


def build_layout() -> list:
    """No-arg entry point for the page registry."""
    from ...data_access import PD_PERFORMANCE_DATA
    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Build the Loss page with top controls and live content."""
    from .....shared.repositories.filters_config import load_filter_config, model_names, segment_values
    from ...domain.loss import set_loss_metrics
    cfg = load_filter_config()
    model_options = model_names("loss")
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
    default_monitoring_point = shared_filters.resolve_monitoring_point_value(monitoring_options, None)

    model_select_options = [{"label": "All models", "value": "all"}] + [{"label": name, "value": name} for name in model_options]

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
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
                                    "Model Use Case / Cycle",
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
                                _build_loss_apply_button(),
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
                        children=build_loss_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
