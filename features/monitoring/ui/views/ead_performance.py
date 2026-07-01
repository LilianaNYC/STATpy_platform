"""Layout for the EAD Performance page.

Ports ``monitoring_ead_performance_layout.py`` from the integrated branch,
adapting imports to the ``features/monitoring/pages/`` package structure used
on ``main``.
"""

from __future__ import annotations

from dash import dcc, html

from .....shared.ui.charts import (
    build_ead_calibration_rag_trend_figure,
    build_ead_discrimination_rag_trend_figure,
    build_ead_metric_trend_figure,
)
from .....shared.ui import controls as shared_filters
from .....shared.ui.controls import build_chart_header
from .....shared.domain.calculations import pd_tone_class
from .....shared.domain.mev_range import (
    calculate_pd_mev_thresholds,
    calculate_pd_mev_worst_rag_after_quarter,
    format_pd_mev_value,
    get_mev_selected_models_simple,
    get_pd_mev_available_names_for_models,
    get_ead_mev_chart_id,
    get_pd_mev_model_development_dates,
    get_pd_mev_scenario_quarter,
)
from .....shared.domain.quarter_labels import iso_date_to_pd_quarter
from .....shared.ui.charts import build_pd_mev_range_figure
from .....shared.theme import normalize_theme_value
from ...domain.ead import (
    build_ead_calibration_rag_trend,
    build_ead_discrimination_rag_trend,
    build_ead_period_summary,
    get_ead_monitoring_point_options,
    get_ead_thresholds,
)
from ...data_access import PD_PERFORMANCE_DATA
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

CONTENT_ID = "ead-dashboard-content"
APPLY_FILTERS_ID = "ead-apply-filters"
APPLIED_FILTERS_STORE_ID = "ead-applied-filters-store"
REPORTING_CYCLE_ID = "ead-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "ead-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "ead-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "ead-reporting-cycle"
SCENARIO_ID = "ead-scenario"
SCENARIO_TOGGLE_ID = "ead-scenario-toggle"
SCENARIO_MENU_ID = "ead-scenario-menu"
SCENARIO_FILTER_KEY = "ead-scenario"
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
SCENARIO_RANKING_STORE_ID = "ead-scenario-ranking-store"
SCENARIO_RANKING_FILTER_ID = "ead-scenario-ranking-filter"

_POST_SUBJECTIVE = PostSubjectiveConfig(
    prefix="ead",
    label="EAD",
    model_type="EAD",
    sensitivity_key="ead_sensitivity_projections",
    scenario_filter_id=SCENARIO_RANKING_FILTER_ID,
)
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


def _build_filter(label: str, component) -> html.Div:
    return html.Div(className="monitoring-filter", children=[html.Label(label), component])


def _subnav_link(section_id: str, label: str, active: bool = False) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


MEV_RANGE_KEY = "ead_mev"

# ---------------------------------------------------------------------------
# MEV Range helpers (mirroring PD Performance)
# ---------------------------------------------------------------------------


def _build_ead_mev_threshold_chips(thresholds: dict | None) -> list:
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


def _ead_mev_marker_legend_item(
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


def _build_ead_mev_marker_items(
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
        _ead_mev_marker_legend_item("Scenario", scenario, "series", line_color=scenario_color, line_dash="solid")
    )
    development_date = (mev_data.get("dev_range") or {}).get("development_date")
    if development_date:
        dev_label = str(development_date).replace("-Q", "Q")
        items.append(_ead_mev_marker_legend_item("Development Date", dev_label, "development"))
    scenario_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
    if scenario_quarter:
        items.append(
            _ead_mev_marker_legend_item("Scenario Date", str(scenario_quarter).replace("-Q", "Q"), "current")
        )
    return items


def _build_ead_mev_monitoring_summary(
    thresholds: dict | None,
    model_data: dict,
    mev_data: dict,
    monitoring_point: str | None,
    theme_value: str | None = None,
    scenario: str = "intsevere",
    reporting_cycle: str | None = None,
):
    threshold_items = _build_ead_mev_threshold_chips(thresholds)
    marker_items = _build_ead_mev_marker_items(
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


def _ead_mev_rag_sort_weight(rag: str) -> int:
    return {"Red": 0, "Amber": 1, "Green": 2}.get(rag, 3)


def _format_ead_mev_quarter(value: str | None) -> str:
    if not value:
        return "—"
    return str(value).replace("-Q", "Q")


def _build_ead_mev_rag_summary_panel(
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
        worst = min(mev_rags, key=lambda e: _ead_mev_rag_sort_weight(e["rag"]))["rag"] if mev_rags else "N/A"
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
                html.Div("No EAD models in scope", className="pd-mev-chart-title"),
                html.P("Adjust the dashboard filters above to bring models into scope.", className="pd-section-subtitle"),
            ],
        )

    model_rows = []
    for summary in summaries:
        dev_label = " / ".join(_format_ead_mev_quarter(d) for d in summary["development_dates"]) if summary["development_dates"] else "—"
        severe_label = _format_ead_mev_quarter(summary["severe_quarter"]) if summary["severe_quarter"] else (monitoring_point or "—")

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


def _build_ead_mev_range_section(
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
    selected_models = get_mev_selected_models_simple(catalog, selected_model, selected_segment, model_type="EAD")

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
            chart_id = get_ead_mev_chart_id(model_name, mev_name)
            theme = normalize_theme_value(theme_value)
            trace_color = "#fb7185" if theme == "dark" else "#dc2626"
            fig = build_pd_mev_range_figure(
                model_data, mev_name, mev_data, trace_color,
                range_store.get("mev"),
                theme=theme,
                reporting_cycle=reporting_cycle,
                scenario=scenario,
            )
            monitoring_summary = _build_ead_mev_monitoring_summary(
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
                                            _format_ead_mev_quarter(scenario_quarter),
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
                "Adjust the model or segment filters above, or check that the MEV catalog contains EAD model data.",
                className="pd-section-subtitle",
            ),
        ],
    )

    body = model_panels if (selected_models and available_mev_names and model_panels) else [empty_state]

    return html.Section(
        id="ead-mev-range",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.5 MEV Range",
                "MEV Range",
                "Checks whether the macro-economic variables (MEVs) driving EAD models under stress remain within their trained operating range.",
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
            _build_ead_mev_rag_summary_panel(
                selected_models, catalog, monitoring_point,
                reporting_cycle=reporting_cycle, scenario=scenario,
            ),
            *body,
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
                            _subnav_link("ead-post-subjective-overview", "Overview"),
                            _subnav_link("ead-psi", "PSI"),
                            _subnav_link("ead-scenario-ranking", "Scenario Ranking"),
                            _subnav_link("ead-sensitivity-analysis", "Sensitivity Analysis"),
                            _subnav_link("ead-mev-range", "MEV Range"),
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
    reporting_cycle: str = "CCAR 2026",
    scenario: str = "intsevere",
    scenario_ranking_store: dict | None = None,
    theme_value: str | None = None,
) -> list:
    theme = normalize_theme_value(theme_value)
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
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "ME", monitoring_point, theme),
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
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "RMSE", monitoring_point, theme),
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
                                figure=build_ead_metric_trend_figure(metric_rows, data["monitoring_thresholds"], "Kendall's Tau", monitoring_point, theme),
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

    mev_range_section = _build_ead_mev_range_section(
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

    executive_summary = build_executive_summary(
        "The EAD Performance dashboard is the monitoring view for Exposure at Default (EAD) models across the "
        "wholesale portfolio. It tracks each model's calibration and discriminatory power against agreed RAG "
        "thresholds, and adds a post subjective review layer (PSI, scenario rank ordering, sensitivity, and MEV "
        "range) so reviewers can judge whether model behaviour remains defensible across reporting cycles and "
        "stress scenarios.",
        theme,
    )

    return [
        executive_summary,
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, calibration_section, discrimination_section]),
        chapter_2,
        html.Div(
            className="pd-chapter-body pd-chapter-body-secondary",
            children=[post_subjective_overview, psi_section, scenario_ranking_section, sensitivity_section, mev_range_section],
        ),
    ]


# ---------------------------------------------------------------------------
# Apply filters UI
# ---------------------------------------------------------------------------


def _build_ead_apply_button() -> html.Div:
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


def build_ead_apply_prompt() -> html.Section:
    return build_getting_started_prompt("EAD", "Exposure at Default")


# ---------------------------------------------------------------------------
# Top-level page builder
# ---------------------------------------------------------------------------


def page_layout() -> list:
    """Build the EAD page with top controls and live content."""
    from .....shared.repositories.filters_config import load_filter_config, model_names, segment_values
    from ...domain.ead import set_ead_metrics
    data = PD_PERFORMANCE_DATA
    cfg = load_filter_config()
    model_options = model_names("ead")
    segment_options = ["All", *segment_values()]
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    scenario_options = [{"label": s["label"], "value": s["value"]} for s in cfg["scenarios"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    default_scenario = scenario_options[0]["value"] if scenario_options else "intsevere"
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
        dcc.Store(id=SCENARIO_RANKING_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("EAD Performance Monitoring Dashboard", className="monitoring-dashboard-title"),
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
                                _build_ead_apply_button(),
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
                        children=build_ead_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
