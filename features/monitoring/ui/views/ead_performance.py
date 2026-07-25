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
from .....shared.ui.controls import build_chart_header, build_section_filter_bar, build_section_filter_item
from .....shared.ui.loading import build_dashboard_loading_shell
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
    get_pd_mev_visible_periods,
)
from .....shared.domain.quarter_labels import iso_date_to_pd_quarter
from .....shared.ui.charts import build_pd_mev_range_figure
from .....shared.theme import normalize_theme_value
from ...domain.actions import select_pd_monitoring_actions
from ...domain.ead import (
    EAD_MODEL_LABEL,
    build_ead_calibration_rag_trend,
    build_ead_discrimination_rag_trend,
    build_ead_period_summary,
    ead_metrics_row_for_quarter,
    get_ead_model_options,
    get_ead_monitoring_point_options,
    get_ead_thresholds,
    get_previous_ead_quarter,
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
    compute_post_subjective_summaries,
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
SEGMENT_TOGGLE_ID = "ead-segment-toggle"
SEGMENT_MENU_ID = "ead-segment-menu"
MONITORING_POINT_TOGGLE_ID = "ead-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "ead-monitoring-point-menu"
MODEL_FILTER_KEY = "ead-model"
SEGMENT_FILTER_KEY = "ead-segment"
MONITORING_POINT_FILTER_KEY = "ead-monitoring-point"
REGION_ID = "ead-region"
REGION_TOGGLE_ID = "ead-region-toggle"
REGION_MENU_ID = "ead-region-menu"
REGION_FILTER_KEY = "ead-region"
PORTFOLIO_ID = "ead-portfolio"
PORTFOLIO_TOGGLE_ID = "ead-portfolio-toggle"
PORTFOLIO_MENU_ID = "ead-portfolio-menu"
PORTFOLIO_FILTER_KEY = "ead-portfolio"
MODEL_GROUP_ID = "ead-model-group"
MODEL_GROUP_TOGGLE_ID = "ead-model-group-toggle"
MODEL_GROUP_MENU_ID = "ead-model-group-menu"
MODEL_GROUP_FILTER_KEY = "ead-model-group"
EAD_SUBNAV_ID = "ead-subnav"
RANGE_STORE_ID = "ead-range-store"
SCENARIO_RANKING_STORE_ID = "ead-scenario-ranking-store"
SCENARIO_RANKING_FILTER_ID = "ead-scenario-ranking-filter"
CONCLUSIONS_NOTES_ID = "ead-conclusions-notes-input"
CONCLUSIONS_NOTES_STORE_ID = "ead-conclusions-notes-store"
EAD_REVIEW_FLOW_OPTION_ID = "ead-review-flow-option"
EAD_REVIEW_FLOW_PENDING_STORE_ID = "ead-review-flow-pending-store"
EAD_REVIEW_FLOW_STATUS_STORE_ID = "ead-review-flow-status-store"
EAD_REVIEW_FLOW_SAVE_ID = "ead-review-flow-save"
EAD_REVIEW_FLOW_SAVE_BAR_ID = "ead-review-flow-save-bar-container"
# Maps this UI's short field keys to the portfolio file's actual column names
# (EAD_Performance_Metrics tab), so reads and writes never drift apart.
EAD_REVIEW_FLOW_COLUMNS = {
    "post_subjective": "rag_post_sr",
    "pre_mitigation": "rag_pre_mitig",
    "post_mitigation": "rag_post_mitig",
}
EAD_REVIEW_FLOW_FIELD_LABELS = {
    "post_subjective": "Post Subjective Review RAG",
    "pre_mitigation": "Pre Mitigation RAG",
    "post_mitigation": "Post Mitigation RAG",
}
# The reviewer sign-off commentary lives in the same portfolio-file mechanism (self-healing column,
# written via the same generic write path) but isn't a RAG, so it's kept out of EAD_REVIEW_FLOW_COLUMNS.
REVIEWER_COMMENTARY_COLUMN = "reviewer_commentary"

_RAG_RANK = {"N/A": -1, "Green": 0, "Amber": 1, "Red": 2}
_RAG_HEX = {"green": "#16a34a", "amber": "#d97706", "red": "#dc2626", "neutral": "#94a3b8"}

_EAD_LIFECYCLE_TOOLTIPS = {
    "performance": (
        "Model RAG (initial) = Performance RAG - Based on the results of tests applied at the modelled outcomes."
    ),
    "subjective_review": (
        "Worst-case RAG across Chapter 2 (Post Subjective Review Analysis): PSI, scenario ranking, sensitivity, "
        "and MEV range findings for the current scope."
    ),
    "post_subjective": (
        "Model RAG (post subjective review) - Reflects the impact of any subjective overlays (this considers the "
        "post-subjective review)."
    ),
    "pre_mitigation": (
        "Pre Mitigation RAG = Pre-Overlay RAG - Obtained from a trend of Model RAG (post subjective review). For ST "
        "models, only the current model RAG (post subjective review) will be considered."
    ),
    "post_mitigation": (
        "Post Mitigation RAG = Post-Overlay RAG - Based on the residual risk of the model. Judgement-based. "
        "Considers compensating controls."
    ),
}

_POST_SUBJECTIVE = PostSubjectiveConfig(
    prefix="ead",
    label="EAD",
    model_type="EAD",
    sensitivity_key="ead_sensitivity_projections",
    scenario_filter_id=SCENARIO_RANKING_FILTER_ID,
    default_segment_model=EAD_MODEL_LABEL,
)
CALIBRATION_SECTION_RANGE_KEY = "ead_calibration_section"
DISCRIMINATION_SECTION_RANGE_KEY = "ead_discrimination_section"
PSI_SECTION_RANGE_KEY = "ead_psi_section"

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
    *,
    reporting_cycle: str,
    scenario: str,
) -> html.Section:
    catalog = data.get("mev_catalog") or {}
    mev_mnemonic_map = data.get("mev_mnemonic_map") or {}
    mev_description_map = data.get("mev_description_map") or {}
    selected_models = get_mev_selected_models_simple(catalog, selected_model, selected_segment, model_type="EAD")

    available_mev_names = get_pd_mev_available_names_for_models(catalog, selected_models, selected_segment)
    mev_periods = get_pd_mev_visible_periods(catalog, selected_models, available_mev_names)

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
    display_filters = []
    if mev_periods:
        display_filters.append(
            build_section_filter_bar([
                build_section_filter_item(
                    "Display filters",
                    range_key="mev",
                    periods=mev_periods,
                    range_value=range_store.get("mev"),
                ),
            ])
        )

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
            *display_filters,
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
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-overview active",
                children=[
                    html.Div("Overview & Conclusion", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("ead-dashboard-overview", "Main Overview", active=True),
                            _subnav_link("ead-conclusions-verdict", "Conclusion"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-rag",
                children=[
                    html.Div("Chapter 1: RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("ead-overview", "RAG Assignment Overview"),
                            _subnav_link("ead-calibration", "Calibration Conservatism"),
                            _subnav_link("ead-discrimination", "Discriminatory Power"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-post-review",
                children=[
                    html.Div("Chapter 2: Post Subjective Review Analysis", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("ead-post-subjective-overview", "Post Subjective Review Analysis Overview"),
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


def _ead_rag_tone(rag: str) -> str:
    return {"Green": "green", "Amber": "amber", "Red": "red"}.get(rag, "neutral")


def _ead_worst_rag(rags: list[str]) -> str:
    rags = [r for r in rags if r]
    return max(rags, key=lambda r: _RAG_RANK.get(r, -1)) if rags else "N/A"


def _count_ead_attention(summaries: list[dict]) -> int:
    return sum(1 for summary in summaries if summary.get("rag") in ("Amber", "Red"))


def _worst_ead_summary(summaries: list[dict]) -> dict | None:
    ranked = [summary for summary in summaries if summary.get("rag") in ("Green", "Amber", "Red")]
    if not ranked:
        return None
    return min(ranked, key=lambda summary: (-_RAG_RANK.get(summary["rag"], -1), summary["name"]))


def _ead_overview_info_chip(tooltip: str | None):
    """Same "?" tooltip chip as ``cards._info_chip``, ported for the 0.0 Overview diagrams."""
    if not tooltip:
        return None
    return html.Span(
        "?",
        className="pd-info-chip",
        role="img",
        **{"aria-label": tooltip, "title": tooltip},
    )


def _build_ead_overview_area_index(index: int, tone: str = "neutral") -> html.Span:
    return html.Span(
        str(index),
        className=f"overview-area-index overview-area-index-{tone}",
        **{"aria-label": f"Overview area {index}"},
    )


def _build_ead_chapter_1_diagram_node(summary: dict, label: str, href: str, extra_class: str = "") -> html.A:
    tone = _ead_rag_tone(summary.get("rag", "N/A"))
    label_children = [label]
    chip = _ead_overview_info_chip(summary.get("tooltip"))
    if chip is not None:
        label_children.append(chip)
    return html.A(
        href=href,
        className=f"overview-chapter-diagram-node overview-chapter-diagram-node-{tone} {extra_class}".strip(),
        children=[
            html.Span(label_children, className="overview-chapter-diagram-node-label"),
            html.Span(
                [pd_rag_dot(summary.get("rag", "N/A")), html.Strong(summary.get("rag", "N/A"))],
                className="overview-chapter-diagram-node-value",
            ),
        ],
        **{"aria-label": f"Jump to {label} section"},
    )


def _build_ead_chapter_1_diagram(chapter_1_rag: str, summaries: list[dict], chapter_1_tooltip: str | None = None) -> html.Div:
    by_name = {summary["name"]: summary for summary in summaries}
    rows = []
    for index, (name, label, href, extra_class) in enumerate([
        ("Calibration Conservatism", "Calibration Conservatism RAG", "#ead-calibration", "overview-chapter-diagram-node-primary"),
        ("Discriminatory Power", "Discriminatory Power RAG", "#ead-discrimination", ""),
    ], start=1):
        summary = by_name.get(name, {"rag": "N/A"})
        node = _build_ead_chapter_1_diagram_node(summary, label, href, extra_class)
        node.children = [_build_ead_overview_area_index(index, _ead_rag_tone(summary["rag"])), *list(node.children)]
        rows.append(node)
        rows.append(html.Span(className=f"overview-chapter-diagram-connector overview-chapter-diagram-connector-{index}", **{"aria-hidden": "true"}))

    tone = _ead_rag_tone(chapter_1_rag)
    rows.append(
        html.Div(
            className=f"overview-chapter-diagram-output overview-chapter-diagram-output-{tone}",
            children=[
                html.Span(
                    ["Performance", html.Br(), "RAG", _ead_overview_info_chip(chapter_1_tooltip)],
                    className="overview-chapter-diagram-output-label",
                ),
                html.Span([pd_rag_dot(chapter_1_rag), html.Strong(chapter_1_rag)], className="overview-chapter-diagram-output-value"),
            ],
        )
    )
    return html.Div(className="overview-chapter-diagram", children=rows)


def _build_ead_chapter_2_overview_card(summary: dict, index: int) -> html.A:
    tone = _ead_rag_tone(summary["rag"])
    return html.A(
        href=f"#{summary['anchor']}",
        className=f"overview-post-review-mini overview-post-review-mini-{tone}",
        children=[
            _build_ead_overview_area_index(index, tone),
            html.Div(
                className="overview-post-review-mini-header",
                children=[html.Strong(summary["name"], className="overview-post-review-mini-title")],
            ),
            html.Div(summary["metric"], className="overview-post-review-mini-value"),
            html.Div(summary["metric_label"], className="overview-post-review-mini-label"),
            html.Div(summary["takeaway"], className="overview-post-review-mini-copy"),
        ],
        **{"aria-label": f"Jump to {summary['name']} section"},
    )


def _build_ead_chapter_2_overview_group(title: str, copy: str, cards: list[html.A], layout_class: str) -> html.Div:
    return html.Div(
        className="overview-post-review-group",
        children=[
            html.Div(
                className="overview-post-review-group-heading",
                children=[
                    html.Span(title, className="overview-post-review-group-kicker"),
                    html.P(copy, className="overview-post-review-group-copy"),
                ],
            ),
            html.Div(
                className=f"overview-post-review-strip {layout_class}",
                children=cards,
            ),
        ],
    )


def _build_ead_chapter_2_overview_strip(summaries: list[dict]) -> html.Div:
    indexed = {
        summary["name"]: _build_ead_chapter_2_overview_card(summary, index)
        for index, summary in enumerate(summaries, start=3)
    }
    core_checks = [indexed[name] for name in ("PSI", "Scenario Ranking") if name in indexed]
    boundary_checks = [indexed[name] for name in ("Sensitivity Analysis", "MEV Range") if name in indexed]
    groups = []
    if core_checks:
        groups.append(
            _build_ead_chapter_2_overview_group(
                "Core stability checks",
                "Start with population stability and ranking order.",
                core_checks,
                "overview-post-review-strip-primary",
            )
        )
    if boundary_checks:
        groups.append(
            _build_ead_chapter_2_overview_group(
                "Stress and boundary checks",
                "Use these to confirm whether shocks or MEV ranges push the model outside expected behaviour.",
                boundary_checks,
                "overview-post-review-strip-secondary",
            )
        )
    return html.Div(className="overview-post-review-board", children=groups)


def _build_ead_overview_chapter_panel(
    kicker: str,
    title: str,
    rag: str,
    body,
    panel_tone: str | None = None,
    show_rag: bool = True,
) -> html.Div:
    tone = panel_tone or _ead_rag_tone(rag)
    rag_tone = _ead_rag_tone(rag)
    return html.Div(
        className=f"overview-chapter-panel overview-chapter-panel-{tone}",
        children=[
            html.Div(
                className="overview-chapter-panel-header",
                children=[
                    html.Div([
                        html.Div(kicker, className="overview-chapter-panel-kicker"),
                        html.H5(title, className="overview-chapter-panel-title"),
                    ]),
                    *(
                        [html.Span(rag, className=f"overview-chapter-panel-rag overview-chapter-panel-rag-{rag_tone}")]
                        if show_rag
                        else []
                    ),
                ],
            ),
            body,
        ],
    )


def _build_ead_main_overview(
    chapter_1_rag: str,
    chapter_1_summaries: list[dict],
    chapter_2_summaries: list[dict],
    chapter_1_tooltip: str | None = None,
) -> html.Section:
    chapter_1_attention = _count_ead_attention(chapter_1_summaries)
    chapter_2_attention = _count_ead_attention(chapter_2_summaries)
    total_areas = len(chapter_1_summaries) + len(chapter_2_summaries)
    total_attention = chapter_1_attention + chapter_2_attention
    chapter_2_rag = _ead_worst_rag([summary.get("rag") for summary in chapter_2_summaries])
    priority_summary = _worst_ead_summary([
        *[{**summary, "chapter": "RAG Assignment"} for summary in chapter_1_summaries],
        *[{**summary, "chapter": "Post Subjective Review Analysis"} for summary in chapter_2_summaries],
    ])
    priority_label = (
        f"{priority_summary['chapter']} -> {priority_summary['name']}"
        if priority_summary and priority_summary.get("rag") in ("Amber", "Red")
        else "No immediate hotspot"
    )
    posture_tone = "red" if any(summary.get("rag") == "Red" for summary in [*chapter_1_summaries, *chapter_2_summaries]) else (
        "amber" if total_attention else "green"
    )

    return html.Section(
        id="ead-dashboard-overview",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "0.0 Overview",
                "Dashboard Main Overview",
                "",
                "N/A",
                options={"show_rag": False},
            ),
            html.Div(
                className="overview-command-hero overview-main-card",
                children=[
                    html.Div(
                        className="overview-main-breakdown",
                        children=[
                            html.Div(
                                className="overview-review-card-heading overview-main-breakdown-heading",
                                children=[
                                    html.Div("Chapter breakdown", className="overview-review-card-kicker"),
                                    html.H4("How the dashboard story splits across the two chapters"),
                                    html.P(
                                        "Each section below keeps the current RAG context so you can spot the stress points quickly."
                                    ),
                                ],
                            ),
                            html.Div(
                                className="overview-chapter-grid overview-chapter-grid-single-card",
                                children=[
                                    _build_ead_overview_chapter_panel(
                                        "Chapter 1",
                                        "RAG Assignment Overview",
                                        chapter_1_rag,
                                        _build_ead_chapter_1_diagram(chapter_1_rag, chapter_1_summaries, chapter_1_tooltip),
                                        panel_tone="neutral",
                                        show_rag=False,
                                    ),
                                    _build_ead_overview_chapter_panel(
                                        "Chapter 2",
                                        "Post Subjective Review Analysis Overview",
                                        chapter_2_rag,
                                        _build_ead_chapter_2_overview_strip(chapter_2_summaries),
                                        panel_tone="neutral",
                                        show_rag=False,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-main-card-scope",
                        children=[
                            html.Div(
                                className="overview-command-hero-copy",
                                children=[
                                    html.Div("Overall posture", className="overview-command-hero-kicker"),
                                    html.H4(
                                        f"{total_attention} of {total_areas} monitored areas need attention",
                                        className="overview-command-hero-title",
                                        style={"--overview-posture-tone": _RAG_HEX[posture_tone], "margin": "0"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-review-focus overview-main-breakdown-focus",
                        children=[
                            html.Div([
                                html.Span("Recommended deep dive"),
                                html.Strong(priority_label),
                            ]),
                            html.Div([
                                html.Span("Why it matters"),
                                html.Strong(
                                    priority_summary["takeaway"]
                                    if priority_summary and priority_summary.get("rag") in ("Amber", "Red")
                                    else "Both chapters are stable for the selected scope."
                                ),
                            ]),
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 3.1 Conclusion: RAG lifecycle diagram + reviewer sign-off + required actions
# ---------------------------------------------------------------------------


def _build_ead_rag_lifecycle_card(
    kicker: str,
    title: str,
    rag: str | None,
    tooltip_key: str,
    extra_class: str = "",
    body=None,
    note: str | None = None,
    href: str | None = None,
):
    tone = _ead_rag_tone(rag) if rag else "neutral"
    children = [
        html.Span(kicker, className="pd-rag-lifecycle-card-kicker"),
        html.Strong([title, _ead_overview_info_chip(_EAD_LIFECYCLE_TOOLTIPS.get(tooltip_key))], className="pd-rag-lifecycle-card-title"),
        body if body is not None else html.Div(
            [pd_rag_dot(rag or "N/A"), html.Strong(rag or "N/A")],
            className="pd-rag-lifecycle-card-value",
        ),
    ]
    if note:
        children.append(html.Span(note, className="pd-rag-lifecycle-card-note"))
    class_name = f"pd-rag-lifecycle-card pd-rag-lifecycle-card-{tone} {extra_class}".strip()
    if href:
        return html.A(
            href=href,
            className=f"{class_name} pd-rag-lifecycle-card-link",
            children=children,
            **{"aria-label": f"Jump to {title} section"},
        )
    return html.Div(className=class_name, children=children)


def _build_ead_rag_lifecycle_merge_badge(symbol: str) -> html.Span:
    return html.Span(symbol, className="pd-rag-lifecycle-merge-badge", **{"aria-hidden": "true"})


def _build_ead_rag_lifecycle_connector() -> html.Span:
    return html.Span(className="pd-rag-lifecycle-connector", **{"aria-hidden": "true"})


def ead_review_flow_rags(selected_model, selected_segment, quarter: str) -> dict[str, str]:
    """Post Subjective Review / Pre Mitigation / Post Mitigation RAG, read verbatim from the portfolio file.

    These three come from the ``EAD_Performance_Metrics`` tab of the portfolio workbook (``rag_post_sr`` /
    ``rag_pre_mitig`` / ``rag_post_mitig``), the same precomputed-metrics store Chapter 1 already reads from --
    they are not derived here.
    """
    row = ead_metrics_row_for_quarter(selected_model, selected_segment, quarter)

    def _text(key: str) -> str:
        value = str(row.get(key, "") or "").strip()
        return value or "N/A"

    return {field: _text(column) for field, column in EAD_REVIEW_FLOW_COLUMNS.items()}


def ead_reviewer_commentary(selected_model, selected_segment, quarter: str) -> str:
    """The reviewer sign-off commentary saved for this scope, or "" if none has been saved yet."""
    row = ead_metrics_row_for_quarter(selected_model, selected_segment, quarter)
    return str(row.get(REVIEWER_COMMENTARY_COLUMN, "") or "").strip()


def _build_ead_rag_lifecycle_metric_list(chapter_2_summaries: list[dict]) -> html.Div:
    """Every Chapter 2 finding with its own RAG -- no single aggregated dot.

    Chapter 2 is a qualitative, subjective-review layer with no defined roll-up formula (unlike Chapter 1's
    weighted Performance RAG), so summarizing it as one dot would imply a computed logic that doesn't exist here.
    """
    return html.Div(
        className="pd-rag-lifecycle-metric-list",
        children=[
            html.Div(
                className="pd-rag-lifecycle-metric-row",
                children=[
                    pd_rag_dot(summary["rag"]),
                    html.Span(summary["name"], className="pd-rag-lifecycle-metric-name"),
                ],
            )
            for summary in chapter_2_summaries
        ],
    )


def _build_ead_review_flow_picker(field: str, effective_value: str | None) -> html.Div:
    """Current value + a "Change RAG" dropdown for an editable review-flow RAG card.

    Picking an option only stages the change (see ``EAD_REVIEW_FLOW_PENDING_STORE_ID``); nothing is
    written to the portfolio file until the reviewer clicks Save in :func:`build_ead_review_flow_save_bar`.
    The dropdown always mounts with ``value=None`` (a "Change RAG to..." action, not a live display of
    the current value) so a fresh mount never looks like a real pick -- see the callback for why that
    matters.
    """
    return html.Div(
        className="pd-rag-picker",
        children=[
            html.Div(
                [pd_rag_dot(effective_value or "N/A"), html.Strong(effective_value or "N/A")],
                className="pd-rag-lifecycle-card-value",
            ),
            html.Label("Change RAG", htmlFor=None, className="pd-rag-picker-label"),
            dcc.Dropdown(
                id={"type": EAD_REVIEW_FLOW_OPTION_ID, "field": field},
                options=[{"label": option, "value": option} for option in ("Green", "Amber", "Red")],
                value=None,
                placeholder="Select…",
                clearable=False,
                searchable=False,
                className="pd-rag-picker-dropdown",
            ),
        ],
    )


def _build_ead_rag_lifecycle_diagram(
    performance_rag: str,
    chapter_2_summaries: list[dict],
    post_subjective_rag: str,
    pre_mitigation_rag: str,
    post_mitigation_rag: str,
    pending_edits: dict | None = None,
) -> html.Div:
    """Performance RAG + Subjective Review = Post Subjective Review -> Pre Mitigation -> Post Mitigation."""
    pending_edits = pending_edits or {}
    effective = {
        field: pending_edits.get(field) or file_value
        for field, file_value in (
            ("post_subjective", post_subjective_rag),
            ("pre_mitigation", pre_mitigation_rag),
            ("post_mitigation", post_mitigation_rag),
        )
    }
    return html.Div(
        className="pd-rag-lifecycle",
        children=[
            _build_ead_rag_lifecycle_card(
                "Chapter 1", "Performance RAG", performance_rag, "performance",
                href="#ead-rag-assignment",
            ),
            _build_ead_rag_lifecycle_merge_badge("+"),
            _build_ead_rag_lifecycle_card(
                "Chapter 2", "Subjective Review", None, "subjective_review",
                extra_class="pd-rag-lifecycle-card-list",
                body=_build_ead_rag_lifecycle_metric_list(chapter_2_summaries),
                href="#ead-post-subjective-overview",
            ),
            _build_ead_rag_lifecycle_merge_badge("="),
            _build_ead_rag_lifecycle_card(
                "Model RAG", "Post Subjective Review RAG", effective["post_subjective"], "post_subjective",
                extra_class="pd-rag-lifecycle-card-highlight",
                body=_build_ead_review_flow_picker("post_subjective", effective["post_subjective"]),
            ),
            _build_ead_rag_lifecycle_connector(),
            _build_ead_rag_lifecycle_card(
                "Pre-Overlay RAG", "Pre Mitigation RAG", effective["pre_mitigation"], "pre_mitigation",
                body=_build_ead_review_flow_picker("pre_mitigation", effective["pre_mitigation"]),
            ),
            _build_ead_rag_lifecycle_connector(),
            _build_ead_rag_lifecycle_card(
                "Post-Overlay RAG", "Post Mitigation RAG", effective["post_mitigation"], "post_mitigation",
                body=_build_ead_review_flow_picker("post_mitigation", effective["post_mitigation"]),
            ),
        ],
    )


def build_ead_review_flow_save_bar(
    pending_edits: dict,
    current_values: dict,
    save_status: str | None,
    commentary_changed: bool = False,
) -> html.Div | None:
    """Diff summary + Save button for staged RAG edits and/or reviewer commentary, plus the last save status."""
    changed = {
        field: value for field, value in (pending_edits or {}).items()
        if value in ("Green", "Amber", "Red") and value != current_values.get(field)
    }
    children = []
    if changed or commentary_changed:
        items = [
            html.Li([
                html.Strong(EAD_REVIEW_FLOW_FIELD_LABELS.get(field, field)),
                f": {current_values.get(field, 'N/A')} → {value}",
            ])
            for field, value in changed.items()
        ]
        if commentary_changed:
            items.append(html.Li([html.Strong("Reviewer sign-off commentary"), ": will be updated"]))
        children.extend([
            html.Div("Unsaved changes to the portfolio file", className="pd-review-flow-save-title"),
            html.Ul(items, className="pd-review-flow-save-list"),
            html.Button(
                "Save to portfolio.xlsx", id=EAD_REVIEW_FLOW_SAVE_ID, type="button", n_clicks=0,
                className="pd-review-flow-save-button",
            ),
        ])
    if save_status:
        children.append(html.Div(save_status, className="pd-review-flow-save-status"))
    if not children:
        return None
    return html.Div(className="pd-review-flow-save-bar", children=children)


def _build_ead_conclusions_signoff_chip(post_mitigation_rag: str) -> html.Div:
    """Read-only Post Mitigation RAG readout (from the portfolio file) alongside the sign-off notes."""
    if post_mitigation_rag in ("Green", "Amber", "Red"):
        tone = _ead_rag_tone(post_mitigation_rag)
        label = ["Post Mitigation RAG: ", html.Strong(post_mitigation_rag)]
    else:
        tone = "neutral"
        label = "Post Mitigation RAG is not available in the portfolio file for this scope."
    return html.Div(
        className=f"pd-conclusions-signoff-chip pd-conclusions-signoff-chip-{tone}",
        children=[pd_rag_dot(post_mitigation_rag or "N/A"), html.Span(label)],
    )


def _build_ead_collapsible_card(card_id: str, title: str, subtitle: str, body: list, extra_class: str = "") -> html.Details:
    """A section-card that folds via native ``<details>``/``<summary>`` (no callbacks)."""
    return html.Details(
        id=card_id,
        className=f"section-card pd-collapsible-card {extra_class}".strip(),
        open=False,
        children=[
            html.Summary(
                className="pd-collapsible-summary",
                children=[
                    html.Span(
                        className="pd-collapsible-summary-copy",
                        children=[
                            html.Span(title, className="section-title"),
                            html.Span(subtitle, className="pd-section-subtitle"),
                        ],
                    ),
                    html.Span("▾", className="pd-collapsible-chevron", **{"aria-hidden": "true"}),
                ],
            ),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# Required Actions panel (governance playbook, driven by the review-flow RAGs)
# ---------------------------------------------------------------------------

_EAD_ACTION_STAGE_KICKERS = {
    "Pre Mitigation": "Pre mitigation playbook",
    "Post Mitigation": "Post mitigation playbook",
}


def _ead_action_empty_hint(selection: dict) -> str:
    labels = [EAD_REVIEW_FLOW_FIELD_LABELS.get(field, field) for field, _ in selection["drivers"]]
    named = " or ".join(labels) if labels else "review-flow RAG"
    return f"Set the {named} above to surface its required action."


def _build_ead_action_governance_pill(label: str, value: str) -> html.Span:
    required = str(value or "").strip().lower() == "yes"
    return html.Span(
        className=f"pd-action-gov-pill{' pd-action-gov-pill-required' if required else ''}",
        children=[html.Span(label), html.Strong("Yes" if required else "No")],
    )


def _build_ead_action_driver_chips(selection: dict, pending_fields: set[str]) -> html.Div:
    chips = []
    for field, rag in selection["drivers"]:
        label = EAD_REVIEW_FLOW_FIELD_LABELS.get(field, field)
        chip_children = [pd_rag_dot(rag), html.Span(f"{label}: "), html.Strong(rag)]
        if field in pending_fields:
            chip_children.append(html.Span("unsaved", className="pd-action-driver-chip-unsaved"))
        chips.append(html.Span(chip_children, className="pd-action-driver-chip"))
    return html.Div(
        className="pd-action-driver-row",
        children=[html.Span("Driven by", className="pd-action-driver-label"), *chips],
    )


def _build_ead_action_card(selection: dict, pending_fields: set[str]) -> html.Article:
    stage = selection["stage"]
    kicker = _EAD_ACTION_STAGE_KICKERS.get(stage, stage)
    action = selection.get("action")

    if not action:
        return html.Article(
            className="pd-test-card pd-test-neutral pd-action-card pd-action-card-empty",
            children=[
                html.Div(
                    className="pd-test-card-heading",
                    children=[html.Div([
                        html.Span(kicker),
                        html.Div([html.H4(f"{stage} action")], className="pd-card-title-row"),
                    ])],
                ),
                _build_ead_action_driver_chips(selection, pending_fields),
                html.Div("No action defined", className="pd-test-value"),
                html.Div(_ead_action_empty_hint(selection), className="pd-test-meta"),
            ],
        )

    tone = _ead_rag_tone(selection["rag"])
    detail_blocks = [
        html.Div(
            className="pd-action-detail pd-action-detail-primary",
            children=[html.Span("Required action"), html.P(action["required_action"])],
        ),
    ]
    if action.get("additional_requirements"):
        detail_blocks.append(
            html.Div(
                className="pd-action-detail",
                children=[html.Span("Additional requirements"), html.P(action["additional_requirements"])],
            )
        )
    if action.get("escalation"):
        detail_blocks.append(
            html.Div(
                className="pd-action-detail",
                children=[html.Span("Escalation / discussion"), html.P(action["escalation"])],
            )
        )

    children = [
        html.Div(
            className="pd-test-card-heading",
            children=[
                html.Div([
                    html.Span(kicker),
                    html.Div([html.H4(action.get("trigger") or f"{stage} action")], className="pd-card-title-row"),
                ]),
                html.Span(
                    [pd_rag_dot(selection["rag"]), html.Strong(selection["rag"])],
                    className="pd-action-card-rag",
                ),
            ],
        ),
    ]
    if selection.get("persistent_breach"):
        children.append(
            html.Div(
                "Persistent breach — two consecutive Red quarters",
                className="pd-action-breach-ribbon",
            )
        )
    children.extend([
        _build_ead_action_driver_chips(selection, pending_fields),
        html.Div(action.get("description", ""), className="pd-action-description"),
        *detail_blocks,
        html.Div(
            className="pd-action-gov-row",
            children=[
                _build_ead_action_governance_pill("Sponsor approval", action.get("sponsor_approval")),
                _build_ead_action_governance_pill("Deep dive", action.get("deep_dive")),
                _build_ead_action_governance_pill("Redevelopment", action.get("redevelopment")),
            ],
        ),
        html.Div(
            " · ".join(
                part for part in (
                    f"Owner: {action.get('owner')}" if action.get("owner") else "",
                    f"Due in: {action.get('due_in_report')}" if action.get("due_in_report") else "",
                ) if part
            ),
            className="pd-test-footnote",
        ),
    ])
    return html.Article(
        className=f"pd-test-card pd-test-{tone} pd-action-card"
                  f"{' pd-action-card-breach' if selection.get('persistent_breach') else ''}",
        children=children,
    )


def _build_ead_required_actions_panel(
    monitoring_actions: list[dict],
    effective_rags: dict[str, str],
    previous_post_mitigation_rag: str,
    pending_fields: set[str],
) -> html.Div | None:
    """Governance playbook actions for the effective review-flow RAGs."""
    if not monitoring_actions:
        return None
    selections = select_pd_monitoring_actions(monitoring_actions, effective_rags, previous_post_mitigation_rag)

    return _build_ead_collapsible_card(
        "ead-conclusions-action-plan",
        "Required actions",
        "Governance playbook actions matched to the review-flow RAGs above. Changing a RAG — even before "
        "saving — updates these actions immediately.",
        [
            html.Div(
                className="pd-action-plan-grid",
                children=[_build_ead_action_card(selection, pending_fields) for selection in selections],
            ),
            html.Div(
                "Source: statpy_monitoring_thresholds.xlsx · monitoring_actions. Each action keys off the review-flow RAG named in "
                "its Trigger column; two consecutive Red Post Mitigation quarters escalate to the persistent-breach "
                "protocol.",
                className="pd-test-footnote",
            ),
        ],
        extra_class="pd-action-plan-card",
    )


def _build_ead_conclusions_verdict_section(
    chapter_1_rag: str,
    chapter_2_summaries: list[dict],
    review_flow_rags: dict[str, str],
    conclusions_notes: str | None = None,
    pending_edits: dict | None = None,
    review_flow_save_status: str | None = None,
    saved_commentary: str = "",
    monitoring_actions: list[dict] | None = None,
    previous_post_mitigation_rag: str = "",
) -> html.Section:
    lifecycle_diagram = _build_ead_rag_lifecycle_diagram(
        chapter_1_rag, chapter_2_summaries,
        review_flow_rags["post_subjective"], review_flow_rags["pre_mitigation"], review_flow_rags["post_mitigation"],
        pending_edits=pending_edits,
    )
    effective_rags = {
        field: (pending_edits or {}).get(field) or review_flow_rags[field]
        for field in ("post_subjective", "pre_mitigation", "post_mitigation")
    }
    pending_fields = {
        field for field, value in (pending_edits or {}).items()
        if value in ("Green", "Amber", "Red") and value != review_flow_rags.get(field)
    }
    actions_panel = _build_ead_required_actions_panel(
        monitoring_actions or [], effective_rags, previous_post_mitigation_rag, pending_fields,
    )
    commentary_changed = (conclusions_notes or "") != (saved_commentary or "")
    save_bar = build_ead_review_flow_save_bar(
        pending_edits or {}, review_flow_rags, review_flow_save_status, commentary_changed,
    )

    reviewer_signoff = _build_ead_collapsible_card(
        "ead-conclusions-reviewer",
        "Reviewer sign-off",
        "Record the reviewer's conclusions, caveats, or rationale for the Post Mitigation RAG shown above.",
        [
            _build_ead_conclusions_signoff_chip(review_flow_rags["post_mitigation"]),
            dcc.Textarea(
                id=CONCLUSIONS_NOTES_ID,
                value=conclusions_notes or "",
                placeholder="Record conclusions, caveats, or a sign-off note for this monitoring cycle...",
                className="pd-conclusions-textarea",
            ),
            html.Div(
                "Saved to portfolio.xlsx via the Save button above once edited.",
                className="pd-test-footnote",
            ),
        ],
        extra_class="pd-conclusions-notes-card",
    )

    return html.Section(
        id="ead-conclusions-verdict",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "3.1 Conclusion", "Conclusion",
                "Synthesizes Chapter 1 (RAG Assignment) and Chapter 2 (Post Subjective Review Analysis) into a "
                "single model verdict, plus the reviewer's own sign-off, for the current scope.",
                "N/A", options={"show_rag": False},
            ),
            lifecycle_diagram,
            *([actions_panel] if actions_panel is not None else []),
            reviewer_signoff,
            html.Div(
                id=EAD_REVIEW_FLOW_SAVE_BAR_ID,
                children=[save_bar] if save_bar is not None else [],
            ),
        ],
    )




def render_ead_performance_content(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
    range_store: dict | None = None,
    *,
    reporting_cycle: str,
    scenario: str,
    scenario_ranking_store: dict | None = None,
    theme_value: str | None = None,
    conclusions_notes: str | None = None,
    review_flow_pending_edits: dict | None = None,
    review_flow_save_status: str | None = None,
) -> list:
    model_options = get_ead_model_options(data)
    if (not selected_model or selected_model == "all") and (selected_segment in (None, "", "All", "all")):
        selected_model = model_options[0] if model_options else selected_model

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
                "At-a-glance summary of the 1-year EAD monitoring flow from metric tests to dimension RAGs and Performance RAG.",
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
                "Compares realized EAD against predicted EAD using mean error and RMSE across the monitored 1-year population.",
                summary["calibration_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-test-grid-3", children=calibration_cards),
            build_section_filter_bar([
                build_section_filter_item(
                    "Display filters",
                    range_key=CALIBRATION_SECTION_RANGE_KEY,
                    periods=calibration_rag_periods,
                    range_value=range_store.get(CALIBRATION_SECTION_RANGE_KEY),
                ),
            ]),
            html.Div(
                id="ead-calibration-rag-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Calibration Conservatism RAG Trend",
                        "Quarter-by-quarter Calibration Conservatism RAG shown as a simple color-coded dot timeline.",
                    ),
                    dcc.Graph(
                        id="ead-calibration-rag-trend-chart",
                        figure=build_ead_calibration_rag_trend_figure(
                            calibration_rag_trend,
                            monitoring_point,
                            range_store.get(CALIBRATION_SECTION_RANGE_KEY),
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
                            ),
                            dcc.Graph(
                                id="ead-me-trend-chart",
                                figure=build_ead_metric_trend_figure(
                                    metric_rows,
                                    data["monitoring_thresholds"],
                                    "ME",
                                    monitoring_point,
                                    theme,
                                    range_store.get(CALIBRATION_SECTION_RANGE_KEY),
                                ),
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
                            ),
                            dcc.Graph(
                                id="ead-rmse-trend-chart",
                                figure=build_ead_metric_trend_figure(
                                    metric_rows,
                                    data["monitoring_thresholds"],
                                    "RMSE",
                                    monitoring_point,
                                    theme,
                                    range_store.get(CALIBRATION_SECTION_RANGE_KEY),
                                ),
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
                "Assesses whether higher predicted EAD observations rank consistently with higher realized EAD outcomes across the monitored 1-year population.",
                summary["discrimination_rag"],
                {"show_rag": False},
            ),
            html.Div(className="pd-test-grid", style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"}, children=discrimination_cards),
            build_section_filter_bar([
                build_section_filter_item(
                    "Display filters",
                    range_key=DISCRIMINATION_SECTION_RANGE_KEY,
                    periods=discrimination_rag_periods,
                    range_value=range_store.get(DISCRIMINATION_SECTION_RANGE_KEY),
                ),
            ]),
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
                            ),
                            dcc.Graph(
                                id="ead-discrimination-rag-trend-chart",
                                figure=build_ead_discrimination_rag_trend_figure(
                                    discrimination_rag_trend,
                                    monitoring_point,
                                    range_store.get(DISCRIMINATION_SECTION_RANGE_KEY),
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
                            ),
                            dcc.Graph(
                                id="ead-kendall-trend-chart",
                                figure=build_ead_metric_trend_figure(
                                    metric_rows,
                                    data["monitoring_thresholds"],
                                    "Kendall's Tau",
                                    monitoring_point,
                                    theme,
                                    range_store.get(DISCRIMINATION_SECTION_RANGE_KEY),
                                ),
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
                "Qualitative review of population stability, scenario ranking, sensitivity, and MEV range. No "
                "standalone chapter RAG is assigned, but material concerns identified here inform the overall Model RAG.",
            ),
        ],
    )

    mev_range_section = _build_ead_mev_range_section(
        data, selected_model, selected_segment, monitoring_point,
        range_store, theme_value=theme_value, reporting_cycle=reporting_cycle, scenario=scenario,
    )

    model, segment = resolve_entity(selected_model, selected_segment, _POST_SUBJECTIVE.default_segment_model)
    chapter_2_summaries = compute_post_subjective_summaries(
        _POST_SUBJECTIVE, data, model, segment, reporting_cycle, scenario, monitoring_point,
        summary, thresholds, selected_model, selected_segment, scenario_ranking_store,
    )
    post_subjective_overview = build_overview_section(
        _POST_SUBJECTIVE, data, model, segment, reporting_cycle, scenario, monitoring_point,
        summary, thresholds, selected_model, selected_segment, scenario_ranking_store,
        summaries=chapter_2_summaries,
    )
    psi_section = build_psi_section(
        _POST_SUBJECTIVE,
        summary,
        thresholds,
        monitoring_point,
        theme,
        range_store=range_store,
        psi_range_key=PSI_SECTION_RANGE_KEY,
    )
    scenario_ranking_section = build_scenario_ranking_section(
        _POST_SUBJECTIVE, data, model, segment, reporting_cycle, monitoring_point, scenario_ranking_store, theme=theme,
    )
    sensitivity_section = build_sensitivity_section(
        _POST_SUBJECTIVE, data, model, segment, reporting_cycle, monitoring_point, theme=theme,
    )

    chapter_1_summaries = [
        {
            "name": "Calibration Conservatism",
            "rag": summary["calibration_rag"],
            "takeaway": "Combines mean error and RMSE against realized EAD.",
        },
        {
            "name": "Discriminatory Power",
            "rag": summary["discrimination_rag"],
            "takeaway": "Reflects Kendall's Tau rank-ordering strength.",
        },
    ]
    dashboard_overview = _build_ead_main_overview(
        summary["performance_rag"], chapter_1_summaries, chapter_2_summaries,
    )

    chapter_3 = html.Section(
        id="ead-conclusions",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "3.",
                "Conclusions",
                "Synthesizes both chapters into a final model verdict and recommendation, plus a place for the "
                "reviewer to record their own conclusions and sign-off for this monitoring cycle.",
                options={"note": f"Monitoring point {monitoring_point}"},
            ),
        ],
    )
    review_flow_rags = ead_review_flow_rags(selected_model, selected_segment, monitoring_point)
    saved_commentary = ead_reviewer_commentary(selected_model, selected_segment, monitoring_point)
    previous_monitoring_point = get_previous_ead_quarter(data, selected_model, selected_segment, monitoring_point)
    previous_review_flow_rags = ead_review_flow_rags(selected_model, selected_segment, previous_monitoring_point)
    section_3_1 = _build_ead_conclusions_verdict_section(
        summary["performance_rag"], chapter_2_summaries, review_flow_rags,
        conclusions_notes=conclusions_notes if conclusions_notes else saved_commentary,
        pending_edits=review_flow_pending_edits,
        review_flow_save_status=review_flow_save_status,
        saved_commentary=saved_commentary,
        monitoring_actions=data.get("monitoring_actions") or [],
        previous_post_mitigation_rag=previous_review_flow_rags["post_mitigation"],
    )
    chapter_3_body = html.Div(
        className="pd-chapter-body pd-chapter-body-conclusions",
        children=[section_3_1],
    )

    executive_summary = build_executive_summary(
        "The EAD Performance dashboard is the monitoring view for Exposure at Default (EAD) models across the "
        "wholesale portfolio. It tracks each model's calibration and discriminatory power against agreed RAG "
        "thresholds, and adds a post subjective review layer (PSI, scenario rank ordering, sensitivity, and MEV "
        "range) so reviewers can judge whether model behaviour remains defensible across model use case / cycles and "
        "stress scenarios.",
        theme,
    )

    return [
        executive_summary, dashboard_overview,
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, calibration_section, discrimination_section]),
        chapter_2,
        html.Div(
            className="pd-chapter-body pd-chapter-body-secondary",
            children=[post_subjective_overview, psi_section, scenario_ranking_section, sensitivity_section, mev_range_section],
        ),
        chapter_3, chapter_3_body,
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
    from .....shared.domain.mev_range import model_field_values
    from .....shared.repositories.filters_config import load_filter_config, model_names, segment_values
    from ...domain.ead import set_ead_metrics
    data = PD_PERFORMANCE_DATA
    cfg = load_filter_config()
    model_options = model_names("ead")
    segment_options = ["All", *segment_values()]
    mev_catalog = data.get("mev_catalog") or {}
    region_options = [{"label": "All", "value": "All"}] + [
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "region", model_options)
    ]
    portfolio_options = [{"label": "All", "value": "All"}] + [
        {"label": value, "value": value} for value in model_field_values(mev_catalog, "portfolio", model_options)
    ]
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    scenario_options = [{"label": s["label"], "value": s["value"]} for s in cfg["scenarios"]]
    default_cycle = reporting_cycle_options[0]["value"]
    default_scenario = scenario_options[0]["value"]
    cycle_data = (data.get("ead_observations_by_cycle") or {}).get(default_cycle)
    if cycle_data:
        set_ead_metrics(cycle_data.get("metrics_store"), cycle_data.get("quarters"))
    else:
        set_ead_metrics(None, [])
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_options = cycle_quarters if cycle_quarters else get_ead_monitoring_point_options(data, None, "All")
    default_monitoring_point = shared_filters.resolve_monitoring_point_value(monitoring_options, None)

    model_select_options = [{"label": "Select model", "value": ""}] + [{"label": name, "value": name} for name in model_options]

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=SCENARIO_RANKING_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        dcc.Store(id=CONCLUSIONS_NOTES_STORE_ID, storage_type="session", data=""),
        dcc.Store(id=EAD_REVIEW_FLOW_PENDING_STORE_ID, data={}),
        dcc.Store(id=EAD_REVIEW_FLOW_STATUS_STORE_ID, data=""),
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("EAD Performance Monitoring Dashboard", className="monitoring-dashboard-title"),
                        html.Div(
                            className="monitoring-controls saas-top-filter-row monitoring-primary-filter-row",
                            children=[
                                _build_filter(
                                    "Region",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=REGION_ID,
                                        toggle_id=REGION_TOGGLE_ID,
                                        menu_id=REGION_MENU_ID,
                                        filter_key=REGION_FILTER_KEY,
                                        options=region_options,
                                        value="All",
                                    ),
                                ),
                                _build_filter(
                                    "Portfolio",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=PORTFOLIO_ID,
                                        toggle_id=PORTFOLIO_TOGGLE_ID,
                                        menu_id=PORTFOLIO_MENU_ID,
                                        filter_key=PORTFOLIO_FILTER_KEY,
                                        options=portfolio_options,
                                        value="All",
                                    ),
                                ),
                                _build_filter(
                                    "Model Group",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=MODEL_GROUP_ID,
                                        toggle_id=MODEL_GROUP_TOGGLE_ID,
                                        menu_id=MODEL_GROUP_MENU_ID,
                                        filter_key=MODEL_GROUP_FILTER_KEY,
                                        options=[{"label": "EAD", "value": "EAD"}],
                                        value="EAD",
                                    ),
                                ),
                                _build_filter(
                                    "Model",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=MODEL_DROPDOWN_ID,
                                        toggle_id=MODEL_TOGGLE_ID,
                                        menu_id=MODEL_MENU_ID,
                                        filter_key=MODEL_FILTER_KEY,
                                        options=model_select_options,
                                        value="",
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
                                        value="",
                                    ),
                                ),
                            ],
                        ),
                        html.Div(
                            className="monitoring-controls saas-top-filter-row saas-secondary-filter-row",
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
                    children=build_dashboard_loading_shell(
                        content_id=CONTENT_ID,
                        scope_label="Monitoring Dashboard",
                        title="Refreshing dashboard",
                        note="Updating scoped metrics, charts, and summary insights.",
                        children=build_ead_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
