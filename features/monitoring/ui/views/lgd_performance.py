"""Layout for the LGD Performance page."""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from .....shared.ui.charts import (
    build_lgd_calibration_rag_trend_figure,
    build_lgd_discrimination_rag_trend_figure,
    build_lgd_metric_trend_figure,
)
from .....shared.ui import controls as shared_filters
from .....shared.ui.controls import build_chart_header
from .....shared.domain.calculations import (
    fmt_n,
    format_pd_metric,
    pd_tone_class,
)
from .....shared.domain.mev_range import (
    calculate_pd_mev_thresholds,
    calculate_pd_mev_worst_rag_after_quarter,
    format_pd_mev_value,
    get_mev_selected_models_simple,
    get_pd_mev_available_names_for_models,
    get_lgd_mev_chart_id,
    get_pd_mev_model_development_dates,
    get_pd_mev_scenario_quarter,
)
from .....shared.domain.quarter_labels import iso_date_to_pd_quarter
from .....shared.ui.charts import build_pd_mev_range_figure
from .....shared.theme import normalize_theme_value
from ...domain.lgd import (
    LGD_CALIBRATION_METRICS,
    LGD_DISCRIMINATION_METRICS,
    LGD_METRICS,
    build_lgd_calibration_rag_trend,
    build_lgd_discrimination_rag_trend,
    build_lgd_heatmap_rows,
    build_lgd_period_summary,
    get_lgd_monitoring_point_options,
    get_lgd_thresholds,
)
from .cards import (
    build_pd_chapter_heading,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_test_card,
    pd_rag_dot,
)
from .post_subjective import (
    PostSubjectiveConfig,
    build_executive_summary,
    build_getting_started_prompt,
    build_overview_section,
    build_psi_section,
    build_scenario_ranking_section,
    build_sensitivity_section,
    resolve_entity,
)

CONTENT_ID = "lgd-dashboard-content"
APPLY_FILTERS_ID = "lgd-apply-filters"
APPLIED_FILTERS_STORE_ID = "lgd-applied-filters-store"
REPORTING_CYCLE_ID = "lgd-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "lgd-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "lgd-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "lgd-reporting-cycle"
SCENARIO_ID = "lgd-scenario"
SCENARIO_TOGGLE_ID = "lgd-scenario-toggle"
SCENARIO_MENU_ID = "lgd-scenario-menu"
SCENARIO_FILTER_KEY = "lgd-scenario"
MODEL_DROPDOWN_ID = "lgd-model-dropdown"
SEGMENT_DROPDOWN_ID = "lgd-segment-dropdown"
MONITORING_POINT_DROPDOWN_ID = "lgd-monitoring-point-dropdown"
MODEL_TOGGLE_ID = "lgd-model-toggle"
MODEL_MENU_ID = "lgd-model-menu"
MODEL_SELECT_ALL_ID = "lgd-model-select-all"
SEGMENT_TOGGLE_ID = "lgd-segment-toggle"
SEGMENT_MENU_ID = "lgd-segment-menu"
MONITORING_POINT_TOGGLE_ID = "lgd-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "lgd-monitoring-point-menu"
MODEL_FILTER_KEY = "lgd-model"
SEGMENT_FILTER_KEY = "lgd-segment"
MONITORING_POINT_FILTER_KEY = "lgd-monitoring-point"
LGD_SUBNAV_ID = "lgd-subnav"
RANGE_STORE_ID = "lgd-range-store"
SCENARIO_RANKING_STORE_ID = "lgd-scenario-ranking-store"
SCENARIO_RANKING_FILTER_ID = "lgd-scenario-ranking-filter"

_POST_SUBJECTIVE = PostSubjectiveConfig(
    prefix="lgd",
    label="LGD",
    model_type="LGD",
    sensitivity_key="lgd_sensitivity_projections",
    scenario_filter_id=SCENARIO_RANKING_FILTER_ID,
)
CALIBRATION_RAG_RANGE_KEY = "lgd_calibration_rag"
DISCRIMINATION_RAG_RANGE_KEY = "lgd_discrimination_rag"
ME_RANGE_KEY = "lgd_me"
RMSE_RANGE_KEY = "lgd_rmse"
KENDALL_RANGE_KEY = "lgd_kendall"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


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


def _build_lgd_subnav() -> html.Div:
    return html.Div(
        id=LGD_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("lgd-overview", "Overview", active=True),
                            _subnav_link("lgd-calibration", "Calibration Conservatism"),
                            _subnav_link("lgd-discrimination", "Discriminatory Power"),
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
                            _subnav_link("lgd-post-subjective-overview", "Overview"),
                            _subnav_link("lgd-psi", "PSI"),
                            _subnav_link("lgd-scenario-ranking", "Scenario Ranking"),
                            _subnav_link("lgd-sensitivity-analysis", "Sensitivity Analysis"),
                            _subnav_link("lgd-mev-range", "MEV Range"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _build_rag_table(summary: dict) -> html.Div:
    rows = []
    for metric in LGD_CALIBRATION_METRICS:
        rows.append({
            "Area": "Calibration Conservatism",
            "Horizon": "1 year",
            "Metric": metric,
            "Value": _format_value(metric, summary["current"].get(metric)),
            "RAG": summary["metric_rags"].get(metric, "N/A"),
        })
    for metric in LGD_DISCRIMINATION_METRICS:
        rows.append({
            "Area": "Discriminatory Power",
            "Horizon": "1 year",
            "Metric": metric,
            "Value": _format_value(metric, summary["current"].get(metric)),
            "RAG": summary["metric_rags"].get(metric, "N/A"),
        })
    rows.extend([
        {"Area": "Dimension", "Horizon": "1 year", "Metric": "Calibration Conservatism RAG", "Value": "-", "RAG": summary["calibration_rag"]},
        {"Area": "Dimension", "Horizon": "1 year", "Metric": "Discriminatory Power RAG", "Value": "-", "RAG": summary["discrimination_rag"]},
        {"Area": "Performance", "Horizon": "1 year", "Metric": "Performance RAG", "Value": "-", "RAG": summary["performance_rag"]},
    ])

    return html.Div(
        className="overview-table-wrap",
        children=html.Table([
            html.Thead(html.Tr([html.Th("Area"), html.Th("Horizon"), html.Th("Metric"), html.Th("Value"), html.Th("RAG")])),
            html.Tbody([
                html.Tr([
                    html.Td(row["Area"]),
                    html.Td(row["Horizon"]),
                    html.Td(row["Metric"]),
                    html.Td(row["Value"]),
                    html.Td([_rag_dot(row["RAG"]), html.Span(f" {row['RAG']}")]),
                ])
                for row in rows
            ]),
        ]),
    )


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


def _build_lgd_overview_flow(summary: dict) -> html.Div:
    from .cards import (
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
            build_pd_overview_flow_input("LGD", {"note": "1 year monitoring"}),
            className="lgd-flow-input",
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric(
                    "Mean Error 1 year", summary["current"].get("ME"), "percent", me_rag,
                    {"href": "#lgd-calibration"},
                ),
                build_pd_overview_flow_metric(
                    "RMSE 1 year", summary["current"].get("RMSE"), "percent", rmse_rag,
                    {"href": "#lgd-calibration"},
                ),
            ],
            {"incoming": True, "extra_class": "lgd-flow-tests-calibration"},
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric(
                    "Kendall's Tau 1 year", summary["current"].get("Kendall's Tau"), "ratio", tau_rag,
                    {"href": "#lgd-discrimination"},
                ),
            ],
            {"incoming": True, "extra_class": "lgd-flow-tests-discrimination"},
        ),

        build_pd_overview_flow_metric(
            "Calibration Conservatism RAG", calibration_rag, "rag", calibration_rag,
            {
                "is_rag": True,
                "href": "#lgd-calibration",
                "incoming": True,
                "outgoing": True,
                "extra_class": "lgd-flow-dimension-calibration",
            },
        ),

        build_pd_overview_flow_metric(
            "Discriminatory Power RAG", discrimination_rag, "rag", discrimination_rag,
            {
                "is_rag": True,
                "href": "#lgd-discrimination",
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
            **{"aria-label": "LGD monitoring overview process flow"},
        ),
    )


def _build_post_review_table(summary: dict) -> html.Div:
    rows = [
        ("Performance RAG", summary["performance_rag"]),
        ("MEV comments", "No LGD MEV range override is configured in dashboard1 source data."),
        ("Scenario comments", "No LGD scenario override is configured in dashboard1 source data."),
        ("Model RAG (Post Subjective Review)", summary["performance_rag"]),
        ("Pre-Mitigation RAG", summary["performance_rag"]),
        ("Post-Mitigation RAG", summary["performance_rag"]),
    ]
    return html.Div(
        className="overview-table-wrap",
        children=html.Table([
            html.Thead(html.Tr([html.Th("Review Field"), html.Th("Value")])),
            html.Tbody([
                html.Tr([
                    html.Td(label),
                    html.Td([_rag_dot(value), html.Span(f" {value}")]) if value in {"Green", "Amber", "Red", "N/A"} else html.Td(value),
                ])
                for label, value in rows
            ]),
        ]),
    )


def _build_heatmap(data: dict, summary: dict, metrics: list[str] | None = None) -> html.Div:
    metric_rows = summary["metric_rows"]
    periods = [row["Monitoring Period"] for row in metric_rows]
    heatmap_rows = build_lgd_heatmap_rows(data, metric_rows)
    if metrics is not None:
        metric_set = set(metrics)
        heatmap_rows = [row for row in heatmap_rows if row["Metric"] in metric_set]
    return html.Div(
        className="overview-table-wrap",
        children=html.Table([
            html.Thead(html.Tr([html.Th("Metric"), *[html.Th(period) for period in periods]])),
            html.Tbody([
                html.Tr([
                    html.Td(row["Metric"]),
                    *[html.Td(_rag_dot(row.get(period, "N/A"))) for period in periods],
                ])
                for row in heatmap_rows
            ]),
        ]),
    )


def _build_metric_history_table(summary: dict, metrics: list[str] | None = None) -> html.Div:
    rows = summary["metric_rows"]
    metrics = metrics or LGD_METRICS
    return html.Div(
        className="overview-table-wrap lgd-history-table-wrap",
        children=html.Table([
            html.Thead(html.Tr([
                html.Th("Monitoring Point"),
                *[html.Th(metric) for metric in metrics],
                html.Th("Predicted LGD"),
                html.Th("Actual LGD"),
                html.Th("Observations"),
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(row["Monitoring Period"]),
                    *[html.Td(_format_value(metric, row.get(metric))) for metric in metrics],
                    html.Td(_format_value("Predicted LGD", row.get("Predicted LGD"))),
                    html.Td(_format_value("Actual LGD", row.get("Actual LGD"))),
                    html.Td(fmt_n(row.get("Observations"))),
                ])
                for row in rows
            ]),
        ]),
    )


def _build_monitoring_rag_table_section(data: dict, summary: dict, metrics: list[str]) -> html.Div:
    return html.Div(
        className="section-card",
        children=[
            html.Div("Monitoring RAG Table", className="section-title"),
            _build_heatmap(data, summary, metrics),
            html.Div("Metric History", className="section-title lgd-metric-history-title"),
            _build_metric_history_table(summary, metrics),
        ],
    )


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


MEV_RANGE_KEY = "lgd_mev"

# ---------------------------------------------------------------------------
# MEV Range helpers (mirroring PD Performance)
# ---------------------------------------------------------------------------


def _build_lgd_mev_threshold_chips(thresholds: dict | None) -> list:
    if not thresholds:
        return []

    def chip(label, value, tone):
        return html.Span([html.Strong(label), value], className=f"pd-mev-threshold-chip pd-mev-threshold-chip-{tone}")

    return [
        chip("Green", f"{format_pd_mev_value(thresholds['green_min'])} to {format_pd_mev_value(thresholds['green_max'])}", "green"),
        chip("Amber low", f"{format_pd_mev_value(thresholds['amber_lower'])} to {format_pd_mev_value(thresholds['green_min'])}", "amber"),
        chip("Amber high", f"{format_pd_mev_value(thresholds['green_max'])} to {format_pd_mev_value(thresholds['amber_upper'])}", "amber"),
        chip("Red", f"< {format_pd_mev_value(thresholds['amber_lower'])} or > {format_pd_mev_value(thresholds['amber_upper'])}", "red"),
    ]


def _lgd_mev_marker_legend_item(
    label: str,
    value_text: str,
    tone: str,
    *,
    line_color: str | None = None,
    line_dash: str | None = None,
) -> html.Div:
    line_style = {}
    if line_color:
        line_style["borderTopColor"] = line_color
    if line_dash:
        line_style["borderTopStyle"] = line_dash
    return html.Div(
        className=f"pd-mev-marker-legend-item pd-mev-marker-legend-item-{tone}",
        children=[
            html.Span(
                className=f"pd-mev-marker-legend-line pd-mev-marker-legend-line-{tone}",
                style=line_style or None,
                **{"aria-hidden": "true"},
            ),
            html.Span(
                className="pd-mev-marker-legend-copy",
                children=[
                    html.Span(label, className="pd-mev-marker-legend-label"),
                    html.Span(value_text, className="pd-mev-marker-legend-date"),
                ],
            ),
        ],
    )


def _build_lgd_mev_marker_items(
    model_data: dict,
    mev_data: dict,
    monitoring_point: str | None,
    theme_value: str | None = None,
    scenario: str = "intsevere",
    reporting_cycle: str | None = None,
) -> list:
    items = []
    scenario_color = "#fb7185" if normalize_theme_value(theme_value) == "dark" else "#dc2626"
    items.append(
        _lgd_mev_marker_legend_item("Scenario", scenario, "series", line_color=scenario_color, line_dash="solid")
    )
    development_date = (mev_data.get("dev_range") or {}).get("development_date")
    if development_date:
        dev_label = str(development_date).replace("-Q", "Q")
        items.append(_lgd_mev_marker_legend_item("Development Date", dev_label, "development"))
    scenario_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
    if scenario_quarter:
        items.append(
            _lgd_mev_marker_legend_item("Scenario Date", str(scenario_quarter).replace("-Q", "Q"), "current")
        )
    return items


def _build_lgd_mev_monitoring_summary(
    thresholds: dict | None,
    model_data: dict,
    mev_data: dict,
    monitoring_point: str | None,
    theme_value: str | None = None,
    scenario: str = "intsevere",
    reporting_cycle: str | None = None,
):
    threshold_items = _build_lgd_mev_threshold_chips(thresholds)
    marker_items = _build_lgd_mev_marker_items(
        model_data, mev_data, monitoring_point, theme_value,
        scenario=scenario, reporting_cycle=reporting_cycle,
    )
    summary_rows = []
    if threshold_items:
        summary_rows.append(html.Div(threshold_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-thresholds"))
    if marker_items:
        summary_rows.append(html.Div(marker_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-markers"))
    if not summary_rows:
        return None
    return html.Div(summary_rows, className="pd-mev-monitoring-summary", **{"aria-label": "Monitoring summary"})


def _lgd_mev_rag_sort_weight(rag: str) -> int:
    return {"Red": 0, "Amber": 1, "Green": 2}.get(rag, 3)


def _format_lgd_mev_quarter(value: str | None) -> str:
    if not value:
        return "—"
    return str(value).replace("-Q", "Q")


def _build_lgd_mev_rag_summary_panel(
    selected_models: list[str],
    catalog: dict,
    monitoring_point: str | None,
    reporting_cycle: str | None = None,
    scenario: str = "intsevere",
) -> html.Div:
    summaries = []
    for model_name in selected_models:
        model_data = catalog.get(model_name, {})
        severe_quarter = ""
        for mev_data in (model_data.get("mevs") or {}).values():
            severe_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
            if severe_quarter:
                break
        if not severe_quarter:
            severe_quarter = iso_date_to_pd_quarter(model_data.get("severe_scenario_date"))
        dev_dates = get_pd_mev_model_development_dates(model_data)
        contributions = model_data.get("contributions") or {}
        mev_rags = []
        for mev_name, mev_data in (model_data.get("mevs") or {}).items():
            rag = calculate_pd_mev_worst_rag_after_quarter(
                mev_data, severe_quarter,
                reporting_cycle=reporting_cycle, scenario=scenario,
            )
            contrib = contributions.get(mev_name)
            mev_rags.append({"name": mev_name, "rag": rag, "contribution": contrib})
        mev_rags.sort(key=lambda entry: (-(entry.get("contribution") or 0), entry["name"]))
        worst = min(mev_rags, key=lambda e: _lgd_mev_rag_sort_weight(e["rag"]))["rag"] if mev_rags else "N/A"
        summaries.append({
            "model_name": model_name,
            "severe_quarter": severe_quarter,
            "development_dates": dev_dates,
            "mev_rags": mev_rags,
            "worst_rag": worst,
            "segments": model_data.get("segments") or [],
        })

    if not summaries:
        return html.Div(
            className="section-card pd-mev-rag-panel pd-mev-rag-panel-empty",
            children=[
                html.Div("No LGD models in scope", className="pd-mev-chart-title"),
                html.P("Adjust the dashboard filters above to bring models into scope.", className="pd-section-subtitle"),
            ],
        )

    model_rows = []
    for summary in summaries:
        dev_label = " / ".join(_format_lgd_mev_quarter(d) for d in summary["development_dates"]) if summary["development_dates"] else "—"
        severe_label = _format_lgd_mev_quarter(summary["severe_quarter"]) if summary["severe_quarter"] else (monitoring_point or "—")

        strip_segments = []
        for entry in summary["mev_rags"]:
            contrib = entry.get("contribution")
            if contrib is None or contrib <= 0:
                continue
            tone = entry["rag"].lower() if entry["rag"] in ("Green", "Amber", "Red") else "na"
            pct_val = contrib * 100
            pct_label = f"{pct_val:.0f}%"
            strip_segments.append(
                html.Div(
                    className=f"pd-mev-strip-seg pd-mev-strip-seg-{tone}",
                    style={"flex": str(contrib)},
                    title=f"{entry['name']}: {pct_label} — RAG {entry['rag']}",
                    children=[
                        html.Span(entry["name"], className="pd-mev-strip-name"),
                        html.Span(pct_label, className="pd-mev-strip-pct"),
                    ],
                )
            )

        model_rows.append(
            html.Div(
                className="pd-mev-summary-row",
                children=[
                    html.Div(
                        className="pd-mev-summary-row-sidebar",
                        children=[
                            html.Div(summary["model_name"], className="pd-mev-summary-row-name"),
                            html.Div(
                                className="pd-mev-summary-row-meta",
                                children=[
                                    html.Div([html.Span("Segments: "), html.Strong(", ".join(summary["segments"]) if summary["segments"] else "—")]),
                                    html.Div([html.Span("Development date: "), html.Strong(dev_label)]),
                                    html.Div([html.Span("Severe scenario: "), html.Strong(severe_label)]),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="pd-mev-summary-row-body",
                        children=[html.Div(strip_segments, className="pd-mev-strip")],
                    ),
                ],
            )
        )

    return html.Div(
        className="section-card pd-mev-summary-panel",
        children=[
            html.Div(
                className="pd-mev-summary-panel-header",
                children=[
                    html.H4("Post-Scenario MEV Summary", className="pd-mev-summary-panel-title"),
                    html.Span(
                        f"{len(summaries)} model{'s' if len(summaries) != 1 else ''} in scope"
                        f" — contribution weights at development, colored by post-scenario RAG",
                        className="pd-mev-summary-panel-subtitle",
                    ),
                ],
            ),
            html.Div(model_rows, className="pd-mev-summary-rows"),
        ],
    )


def _build_lgd_mev_range_section(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    monitoring_point: str | None,
    range_store: dict,
    theme_value: str | None = None,
    reporting_cycle: str = "CCAR 2026",
    scenario: str = "intsevere",
) -> html.Section:
    catalog = data.get("mev_catalog") or {}
    mev_mnemonic_map = data.get("mev_mnemonic_map") or {}
    mev_description_map = data.get("mev_description_map") or {}
    selected_models = get_mev_selected_models_simple(catalog, selected_model, selected_segment, model_type="LGD")

    available_mev_names = get_pd_mev_available_names_for_models(catalog, selected_models)

    model_panels = []
    for model_name in selected_models:
        model_data = catalog.get(model_name, {})
        mev_entries = sorted(
            ((name, mdata) for name, mdata in (model_data.get("mevs") or {}).items() if name in available_mev_names),
            key=lambda kv: kv[0],
        )
        if not mev_entries:
            continue

        scenario_quarter = ""
        for _, mev_data in mev_entries:
            scenario_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
            if scenario_quarter:
                break

        chart_cards = []
        for mev_name, mev_data in mev_entries:
            mev_mnemonic = mev_mnemonic_map.get(mev_name, mev_name)
            mev_description = mev_description_map.get(mev_name, "")
            thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
            chart_id = get_lgd_mev_chart_id(model_name, mev_name)
            theme = normalize_theme_value(theme_value)
            trace_color = "#fb7185" if theme == "dark" else "#dc2626"
            fig = build_pd_mev_range_figure(
                model_data, mev_name, mev_data, trace_color,
                range_store.get("mev"),
                theme=theme,
                reporting_cycle=reporting_cycle,
                scenario=scenario,
            )
            monitoring_summary = _build_lgd_mev_monitoring_summary(
                thresholds, model_data, mev_data, monitoring_point,
                theme_value, scenario=scenario, reporting_cycle=reporting_cycle,
            )
            chart_cards.append(
                html.Article(
                    className="pd-mev-chart-card",
                    children=[
                        html.Div(
                            className="pd-mev-chart-header",
                            children=[html.Div([
                                html.Div(mev_name, className="pd-mev-chart-title"),
                                html.Div(
                                    f"{mev_mnemonic}: {mev_description}" if mev_description else mev_mnemonic,
                                    className="pd-mev-chart-meta",
                                ),
                            ])],
                        ),
                        monitoring_summary,
                        dcc.Graph(id=chart_id, figure=fig, config=_GRAPH_CONFIG, className="pd-mev-chart"),
                    ],
                )
            )

        model_panels.append(
            html.Div(
                className="section-card pd-mev-model-panel",
                children=[
                    html.Div(
                        className="pd-mev-model-heading",
                        children=[
                            html.Div(
                                className="pd-mev-model-copy",
                                children=[
                                    html.Div("Model Scope", className="pd-content-kicker"),
                                    html.H4(model_name),
                                    html.P(f"Segments covered: {', '.join(model_data.get('segments') or []) or '—'}"),
                                ],
                            ),
                            html.Div(
                                className="pd-mev-model-meta",
                                children=[
                                    html.Div([
                                        html.Span("MEVs", className="pd-mev-model-meta-label"),
                                        html.Span(f"{len(mev_entries)}", className="pd-mev-model-meta-value"),
                                    ], className="pd-mev-model-meta-item"),
                                    html.Div([
                                        html.Span(f"Scenario: {scenario}", className="pd-mev-model-meta-label"),
                                        html.Span(
                                            _format_lgd_mev_quarter(scenario_quarter),
                                            className="pd-mev-model-meta-value pd-mev-model-meta-value-scenario",
                                        ),
                                    ], className="pd-mev-model-meta-item"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(chart_cards, className="pd-mev-chart-grid"),
                ],
            )
        )

    empty_state = html.Div(
        className="section-card pd-mev-empty-state",
        children=[
            html.Div("No MEV charts match the current filters", className="pd-mev-chart-title"),
            html.P(
                "Adjust the model or segment filters above, or check that the MEV catalog contains LGD model data.",
                className="pd-section-subtitle",
            ),
        ],
    )

    body = model_panels if (selected_models and available_mev_names and model_panels) else [empty_state]

    return html.Section(
        id="lgd-mev-range",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.5 MEV Range",
                "MEV Range",
                "Checks whether the macro-economic variables (MEVs) driving LGD models under stress remain within their trained operating range.",
                "N/A",
                options={"show_rag": False},
            ),
            html.Div(
                className="pd-performance-note",
                style={"marginBottom": "16px"},
                children=[
                    html.Strong("How it works: "),
                    "At development time, the model observed a range of MEV values that defined its confidence boundaries. "
                    "Each MEV's current scenario value is compared against these thresholds:",
                    html.Div(
                        style={"display": "flex", "gap": "12px", "marginTop": "8px", "marginBottom": "8px", "flexWrap": "wrap"},
                        children=[
                            html.Span([
                                html.Span("", style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "2px", "background": "rgba(34,197,94,0.5)", "marginRight": "5px", "verticalAlign": "middle"}),
                                html.Strong("Green"), " — within development min / max",
                            ], style={"fontSize": "11px"}),
                            html.Span([
                                html.Span("", style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "2px", "background": "rgba(245,158,11,0.5)", "marginRight": "5px", "verticalAlign": "middle"}),
                                html.Strong("Amber"), " — within ±2 standard deviations",
                            ], style={"fontSize": "11px"}),
                            html.Span([
                                html.Span("", style={"display": "inline-block", "width": "10px", "height": "10px", "borderRadius": "2px", "background": "rgba(239,68,68,0.5)", "marginRight": "5px", "verticalAlign": "middle"}),
                                html.Strong("Red"), " — outside amber boundary",
                            ], style={"fontSize": "11px"}),
                        ],
                    ),
                    "Values in the Red zone indicate the MEV has moved significantly beyond the model's trained operating range, "
                    "which may affect model reliability.",
                ],
            ),
            _build_lgd_mev_rag_summary_panel(
                selected_models, catalog, monitoring_point,
                reporting_cycle=reporting_cycle, scenario=scenario,
            ),
            *body,
        ],
    )


def render_lgd_performance_content(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
    range_store: dict | None = None,
    reporting_cycle: str = "CCAR 2026",
    scenario: str = "intsevere",
    scenario_ranking_store: dict | None = None,
    theme_value: str | None = None,
) -> list:
    theme = normalize_theme_value(theme_value)
    range_store = range_store or {}
    summary = build_lgd_period_summary(data, selected_model, selected_segment, selected_monitoring_point)
    thresholds = get_lgd_thresholds(data)
    context = {
        "snapshot_quarter": summary["monitoring_point"] or "No monitoring point",
        "previous_quarter": summary["previous_monitoring_point"],
    }

    if not summary["current"]:
        return [
            html.Div(
                className="section-card pd-placeholder-card",
                children=[
                    html.Div("No LGD data", className="pd-placeholder-badge"),
                    html.Div("LGD Performance", className="pd-placeholder-title"),
                    html.P("No LGD observations are available for the selected model and segment."),
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
        build_pd_section_rag_card(
            "Performance RAG",
            summary["performance_rag"],
            summary["previous_performance_rag"],
            context,
            {"hide_status": True, "hide_comparison": True, "meta_label": "Monitoring point"},
        ),
    ]

    metric_rows = summary["metric_rows"]
    monitoring_point = summary["monitoring_point"]
    calibration_rag_trend = build_lgd_calibration_rag_trend(data, metric_rows)
    calibration_rag_periods = [row["quarter"] for row in calibration_rag_trend]
    discrimination_rag_trend = build_lgd_discrimination_rag_trend(data, metric_rows)
    discrimination_rag_periods = [row["quarter"] for row in discrimination_rag_trend]

    chapter_1 = html.Section(
        id="lgd-rag-assignment",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "1.",
                "RAG Assignment",
                "Core monitoring view for LGD model health, combining the current overview with calibration "
                "conservatism and discriminatory-power diagnostics.",
                options={"note": f"Monitoring point {monitoring_point}"},
            ),
        ],
    )

    overview_section = html.Section(
        id="lgd-overview",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Overview",
                "LGD RAG Assignment Overview",
                "At-a-glance summary of the 1 year LGD monitoring flow from metric tests to dimension RAGs and Performance RAG.",
                summary["performance_rag"],
                {"show_rag": False},
            ),
            _build_lgd_overview_flow(summary),
        ],
    )

    calibration_section = html.Section(
        id="lgd-calibration",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 Calibration Conservatism",
                "Calibration Conservatism",
                "Compare realized LGD against predicted LGD using mean error and RMSE.",
                summary["calibration_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-test-grid-3", children=calibration_cards),
            html.Div(
                id="lgd-calibration-rag-trend-panel",
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
                        id="lgd-calibration-rag-trend-chart",
                        figure=build_lgd_calibration_rag_trend_figure(
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
                        id="lgd-me-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Mean Error Trend",
                                "Mean error by monitoring point with LGD threshold shading.",
                                ME_RANGE_KEY,
                                calibration_rag_periods,
                                range_store.get(ME_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="lgd-me-trend-chart",
                                figure=build_lgd_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "ME", monitoring_point, theme),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                    html.Div(
                        id="lgd-rmse-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "RMSE Trend",
                                "Root mean squared error by monitoring point with LGD threshold shading.",
                                RMSE_RANGE_KEY,
                                calibration_rag_periods,
                                range_store.get(RMSE_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="lgd-rmse-trend-chart",
                                figure=build_lgd_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "RMSE", monitoring_point, theme),
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
        id="lgd-discrimination",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.3 Discriminatory Power",
                "Discriminatory Power",
                "Assess whether higher predicted LGD observations rank consistently with higher realized LGD outcomes.",
                summary["discrimination_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid", style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"}, children=discrimination_cards[:2]),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
                    html.Div(
                        id="lgd-discrimination-rag-trend-panel",
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
                                id="lgd-discrimination-rag-trend-chart",
                                figure=build_lgd_discrimination_rag_trend_figure(
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
                        id="lgd-kendall-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Kendall's Tau Trend",
                                "Rank-ordering strength by monitoring point with LGD threshold shading.",
                                KENDALL_RANGE_KEY,
                                discrimination_rag_periods,
                                range_store.get(KENDALL_RANGE_KEY),
                            ),
                            dcc.Graph(
                                id="lgd-kendall-trend-chart",
                                figure=build_lgd_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "Kendall's Tau", monitoring_point, theme),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    chapter_1_body = html.Div(
        className="pd-chapter-body pd-chapter-body-primary",
        children=[overview_section, calibration_section, discrimination_section],
    )

    chapter_2 = html.Section(
        id="lgd-post-subjective-review-analysis",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "2.",
                "Post Subjective Review Analysis",
                "Qualitative review and scenario context represented using dashboard1's current LGD source data availability.",
            ),
        ],
    )

    mev_range_section = _build_lgd_mev_range_section(
        data, selected_model, selected_segment, monitoring_point,
        range_store, theme_value=theme_value, reporting_cycle=reporting_cycle, scenario=scenario,
    )

    level, entity = resolve_entity(selected_model, selected_segment)
    post_subjective_overview = build_overview_section(
        _POST_SUBJECTIVE, data, level, entity, reporting_cycle, scenario, monitoring_point,
        summary, thresholds, selected_model, selected_segment, scenario_ranking_store,
    )
    psi_section = build_psi_section(_POST_SUBJECTIVE, summary, thresholds, monitoring_point, theme)
    scenario_ranking_section = build_scenario_ranking_section(
        _POST_SUBJECTIVE, data, level, entity, reporting_cycle, monitoring_point, scenario_ranking_store, theme=theme,
    )
    sensitivity_section = build_sensitivity_section(
        _POST_SUBJECTIVE, data, level, entity, reporting_cycle, monitoring_point, theme=theme,
    )

    chapter_2_body = html.Div(
        className="pd-chapter-body pd-chapter-body-secondary",
        children=[post_subjective_overview, psi_section, scenario_ranking_section, sensitivity_section, mev_range_section],
    )

    executive_summary = build_executive_summary(
        "The LGD Performance dashboard is the monitoring view for Loss Given Default (LGD) models across the "
        "wholesale portfolio. It tracks each model's calibration and discriminatory power against agreed RAG "
        "thresholds, and adds a post subjective review layer (PSI, scenario rank ordering, sensitivity, and MEV "
        "range) so reviewers can judge whether model behaviour remains defensible across reporting cycles and "
        "stress scenarios.",
        theme,
    )

    return [executive_summary, chapter_1, chapter_1_body, chapter_2, chapter_2_body]


def _build_lgd_apply_button() -> html.Div:
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


def build_lgd_apply_prompt() -> html.Section:
    return build_getting_started_prompt("LGD", "Loss Given Default")


def build_layout() -> list:
    """No-arg entry point for the page registry."""
    from ...data_access import PD_PERFORMANCE_DATA
    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Build the LGD page with top controls and live content."""
    from .....shared.repositories.filters_config import load_filter_config, model_names, segment_values
    from ...domain.lgd import set_lgd_metrics
    cfg = load_filter_config()
    model_options = model_names("lgd")
    segment_options = ["All", *segment_values()]
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    scenario_options = [{"label": s["label"], "value": s["value"]} for s in cfg["scenarios"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    default_scenario = scenario_options[0]["value"] if scenario_options else "intsevere"
    cycle_data = (data.get("lgd_observations_by_cycle") or {}).get(default_cycle)
    if cycle_data:
        set_lgd_metrics(cycle_data.get("metrics_store"), cycle_data.get("quarters"))
    else:
        set_lgd_metrics(None, [])
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_options = cycle_quarters if cycle_quarters else get_lgd_monitoring_point_options(data, None, "All")
    default_monitoring_point = monitoring_options[0] if monitoring_options else ""

    model_select_options = [{"label": "All models", "value": "all"}] + [{"label": name, "value": name} for name in model_options]

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=SCENARIO_RANKING_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("LGD Performance Monitoring Dashboard", className="monitoring-dashboard-title"),
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
                                    "Scenario",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=SCENARIO_ID,
                                        toggle_id=SCENARIO_TOGGLE_ID,
                                        menu_id=SCENARIO_MENU_ID,
                                        filter_key=SCENARIO_FILTER_KEY,
                                        options=scenario_options,
                                        value=default_scenario,
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
                                _build_lgd_apply_button(),
                            ],
                        ),
                        html.Div(style={"marginTop": "12px"}, children=[_build_lgd_subnav()]),
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
                        children=build_lgd_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
