"""Layout for the PD Performance page.

Ports ``renderPdModels`` and its supporting section builders
(``buildPdRankOrderingSection``, ``buildPdMevRangeSection``,
``buildPdPlaceholderCard``) from ``pages/monitoring_pd_models_page.py``.

The JS version mutated globals (``CQ``/``PQ``/``PD_CALIBRATION_TREND_HORIZON``/
``PD_DISCRIMINATION_TREND_HORIZON``/``PD_MEV_FILTER_*``) and re-rendered the
whole tab on every change. Here, :func:`render_pd_performance_content` is a
pure function of the global filter state (:class:`PdFilterContext`) plus
three small ``dcc.Store`` payloads (per-chart range selections, trend PD
horizons, and the MEV chart-filter sub-state), and is called by
``callbacks.py`` whenever any of those change.

:func:`page_layout` builds the page's top bar + content for the shared app
shell (:mod:`shell`); :func:`build_stores` returns the ``dcc.Store``
components that hold this page's filter/range state.
"""

from __future__ import annotations

from dash import dcc, html

from .....data.analytics import constants as config
from .....components.charts import (
    build_pd_balance_sheet_calibration_rag_trend_figure,
    build_pd_calibration_rag_trend_figure,
    build_pd_confidence_interval_trend_figure,
    build_pd_default_rate_trend_figure,
    build_pd_discrimination_rag_trend_figure,
    build_pd_discrimination_trend_figures,
    build_pd_go_live_accuracy_trend_figure,
    build_pd_mev_range_figure,
    build_pd_notching_trend_figure,
    build_pd_rank_ordering_figure,
)
from .....components.filters import (
    MEV_MODEL_FILTER_ID,
    MEV_MODEL_MENU_ID,
    MEV_MODEL_TOGGLE_ID,
    MEV_RESET_ID,
    build_chart_header,
    build_frozen_horizon_control,
    build_global_filters,
    build_range_controls,
    build_single_select_dropdown,
    build_trend_horizon_control,
)
from .cards import (
    build_pd_chapter_heading,
    build_pd_ead_card,
    build_pd_overview_heatmap,
    build_pd_section_heading,
    build_pd_section_rag_card,
    build_pd_static_info_card,
    build_pd_test_card,
)
from .....data.analytics.mev_range import (
    calculate_pd_mev_thresholds,
    calculate_pd_mev_worst_rag_after_quarter,
    format_pd_mev_value,
    get_pd_mev_available_names_for_models,
    get_pd_mev_chart_id,
    get_pd_mev_model_development_dates,
    get_pd_mev_selected_models,
    get_pd_mev_visible_periods,
)
from .....data.analytics.rank_ordering import (
    _pd_quarter_sort_key,
    build_pd_rank_ordering_aggregate,
    build_pd_rank_ordering_period_label_map,
    format_pd_date_summary,
    format_pd_short_date,
    get_pd_rank_ordering_selected_facilities,
    iso_date_to_pd_quarter,
)
from .....data.analytics.calculations import (
    PdFilterContext,
    build_pd_balance_sheet_calibration_rag_trend,
    build_pd_calibration_assignment_tooltip,
    build_pd_calibration_rag_trend,
    build_pd_calibration_tooltip,
    build_pd_discrimination_rag_trend,
    build_pd_overview_performance_rag_tooltip,
    build_pd_performance_trend_for_horizon,
    calculate_pd_calibration_assignment_rag,
    calculate_pd_calibration_conservatism_details,
    calculate_pd_default_count_for_horizon,
    calculate_pd_discrimination_section_rag,
    calculate_pd_ead_summaries,
    calculate_pd_metric_rag,
    calculate_pd_notching_components,
    calculate_pd_overview_performance_rag,
    calculate_pd_rag_metrics,
    calculate_pd_rag_metrics_for_horizon,
    filter_pd_performance_observations,
    filter_pd_performance_observations_for_horizon,
    fmt_n,
    get_pd_crr_master_scale,
    get_pd_go_live_quarter,
    get_pd_performance_context,
    get_pd_performance_context_for_horizon,
    get_pd_range_periods,
    get_pd_thresholds,
    get_previous_pd_quarter,
    get_worst_pd_rag,
)

# ---------------------------------------------------------------------------
# Top-level component / store ids
# ---------------------------------------------------------------------------

from .....shared.theme import APP_THEME_ID, normalize_theme_value

CONTENT_ID = "pd-performance-content"
RANGE_STORE_ID = "pd-range-store"
TREND_HORIZON_STORE_ID = "pd-trend-horizon-store"
MEV_FILTER_STORE_ID = "pd-mev-filter-store"

# Maps each per-panel trend-horizon control to the shared store group it
# reads/writes. Ports the JS PD_CALIBRATION_TREND_HORIZON /
# PD_DISCRIMINATION_TREND_HORIZON globals, each of which was rendered as a
# control in multiple chart headers but controlled every instance at once.
TREND_HORIZON_GROUPS = {
    "calibration_ci": "calibration",
    "calibration_notching": "calibration",
    "calibration_default_rate": "calibration",
    "discrimination_trend": "discrimination",
}

DEFAULT_TREND_HORIZON_STORE = {"calibration": "1y", "discrimination": "1y"}
DEFAULT_MEV_FILTER_STORE = {"model": "all", "names": None}

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def _trend_horizon_value(trend_horizon_store: dict | None, group: str) -> str:
    value = (trend_horizon_store or {}).get(group)
    return value if value in ("1y", "2y") else "1y"


# ---------------------------------------------------------------------------
# Placeholder card (buildPdPlaceholderCard)
# ---------------------------------------------------------------------------


def _build_placeholder_card(title: str, message: str, tags: list[str] | None = None) -> html.Div:
    children = [
        html.Div("Placeholder module", className="pd-placeholder-badge"),
        html.Div(title, className="pd-placeholder-title"),
        html.P(message),
    ]
    if tags:
        children.append(html.Div([html.Span(tag) for tag in tags], className="pd-placeholder-tags"))
    return html.Div(children, className="section-card pd-placeholder-card")


# ---------------------------------------------------------------------------
# MEV chart-filter store resolvers (getPdMevChartModelNames / getPdMevChartNames)
# ---------------------------------------------------------------------------


def resolve_pd_mev_chart_model_names(available_models: list[str], store_model: str | None) -> list[str]:
    """Resolve ``pd-mev-filter-store["model"]`` against the dashboard-filtered model list."""
    if not available_models:
        return []
    if store_model in (None, "all") or store_model not in available_models:
        return list(available_models)
    return [store_model]


def resolve_pd_mev_chart_names(available_names: list[str], store_names: list[str] | None) -> list[str]:
    """Resolve ``pd-mev-filter-store["names"]`` against the available MEV names.

    ``None`` means "no explicit selection yet" and resolves to all available
    names. A list (including an empty one) is the user's explicit selection,
    filtered down to names still available under the current model scope.
    """
    if not available_names:
        return []
    if store_names is None:
        return list(available_names)
    return [name for name in store_names if name in available_names]


# ---------------------------------------------------------------------------
# 2.4 Scenario Rank Ordering (buildPdRankOrderingSection)
# ---------------------------------------------------------------------------


def _build_rank_ordering_section(data: dict, ctx: PdFilterContext, range_store: dict) -> html.Section:
    facilities = get_pd_rank_ordering_selected_facilities(data["rank_ordering_facilities"], ctx)
    acl_aggregate = build_pd_rank_ordering_aggregate(facilities, "acl_pd_historical", "acl_pd_forecast")
    nco_aggregate = build_pd_rank_ordering_aggregate(facilities, "nco_pd_historical", "nco_pd_forecast")
    periods = sorted({*acl_aggregate["periods"], *nco_aggregate["periods"]}, key=_pd_quarter_sort_key)
    severe_dates_for_labels = acl_aggregate["severe_dates"] or nco_aggregate["severe_dates"]
    period_label_map = build_pd_rank_ordering_period_label_map(periods, severe_dates_for_labels)
    model_scope = sorted({f["pd_model"] for f in facilities if f.get("pd_model")})
    source_file = data.get("rank_ordering_source_file") or "facilities_dummy_data.json"
    has_data = bool(facilities) and bool(periods)

    range_value = range_store.get("rank_ordering")

    if has_data:
        body = html.Div(
            className="pd-trend-detail-grid",
            children=[
                html.Div(
                    id="pd-rank-ordering-acl-panel",
                    className="section-card pd-default-rate-trend-section",
                    children=[
                        build_chart_header(
                            "Aggregate ACL PD",
                            f"Historical, base, and severe ACL PD for the facilities in scope. "
                            f"Severe scenario date: {format_pd_date_summary(acl_aggregate['severe_dates'])}.",
                        ),
                        dcc.Graph(
                            id="pd-rank-ordering-acl-chart",
                            figure=build_pd_rank_ordering_figure(acl_aggregate, "ACL PD", range_value),
                            config=_GRAPH_CONFIG,
                            className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
                        ),
                    ],
                ),
                html.Div(
                    id="pd-rank-ordering-nco-panel",
                    className="section-card pd-default-rate-trend-section",
                    children=[
                        build_chart_header(
                            "Aggregate NCO PD",
                            f"Historical, base, and severe NCO PD for the facilities in scope. "
                            f"Severe scenario date: {format_pd_date_summary(nco_aggregate['severe_dates'])}.",
                        ),
                        dcc.Graph(
                            id="pd-rank-ordering-nco-chart",
                            figure=build_pd_rank_ordering_figure(nco_aggregate, "NCO PD", range_value),
                            config=_GRAPH_CONFIG,
                            className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
                        ),
                    ],
                ),
            ],
        )
    else:
        body = html.Div(
            className="section-card pd-mev-empty-state",
            children=[
                html.Div("No scenario rank ordering data matches the current dashboard filters", className="pd-mev-chart-title"),
                html.P(
                    "Adjust Segment or Specific Models above to bring facility-level ACL and NCO PD paths into scope.",
                    className="pd-section-subtitle",
                ),
            ],
        )

    if has_data:
        chart_scope_subtitle = (
            f"Simple-average PD paths across {len(facilities)} facilities in scope. Dashboard filters above "
            f"automatically apply to Segment and Specific Models. Models in scope: "
            f"{', '.join(model_scope) or '—'}. Source: {source_file}."
        )
    else:
        chart_scope_subtitle = (
            f"No facility-level PD paths are currently available for the selected Segment and Specific Models "
            f"filters. Source: {source_file}."
        )

    return html.Section(
        id="pd-rank-ordering",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Scenario Rank Ordering",
                "Scenario Rank Ordering",
                "Aggregate ACL PD and NCO PD paths for facilities in scope, comparing historical behaviour with "
                "base and severe scenario projections.",
                "N/A",
                options={"show_rag": False},
            ),
            html.Div(
                className="pd-chart-heading",
                children=[
                    html.Div(
                        className="pd-chart-heading-copy",
                        children=[
                            html.Div("Chart scope", className="section-title"),
                            html.Div(chart_scope_subtitle, className="pd-section-subtitle"),
                        ],
                    ),
                    html.Div(
                        className="pd-chart-actions",
                        children=[build_range_controls("rank_ordering", periods, range_value)] if periods else [],
                    ),
                ],
            ),
            body,
        ],
    )


# ---------------------------------------------------------------------------
# 2.6 MEV Range helpers
# ---------------------------------------------------------------------------


def _build_mev_threshold_chips(thresholds: dict | None) -> list:
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


def _mev_marker_legend_item(
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


def _monitoring_point_to_mev_quarter(monitoring_point: str) -> str:
    """Convert a portfolio quarter label (``YYYYQn``) to an MEV quarter label (``YYYY-Qn``)."""
    if len(monitoring_point) == 6 and monitoring_point[4] == "Q":
        return f"{monitoring_point[:4]}-{monitoring_point[4:]}"
    return monitoring_point


def _build_mev_marker_items(model_data: dict, mev_data: dict, monitoring_point: str | None, theme_value: str | None = None) -> list:
    items = []
    scenario_color = "#fb7185" if normalize_theme_value(theme_value) == "dark" else "#dc2626"
    items.append(
        _mev_marker_legend_item("Scenario", "Severe", "series", line_color=scenario_color, line_dash="solid")
    )
    development_date = (mev_data.get("dev_range") or {}).get("development_date")
    if development_date:
        dev_label = str(development_date).replace("-Q", "Q")
        items.append(_mev_marker_legend_item("Development Date", dev_label, "development"))
    if monitoring_point:
        items.append(
            _mev_marker_legend_item("Scenario Date", monitoring_point, "current")
        )
    return items


def _build_mev_monitoring_summary(
    thresholds: dict | None, model_data: dict, mev_data: dict, monitoring_point: str | None, theme_value: str | None = None,
):
    threshold_items = _build_mev_threshold_chips(thresholds)
    marker_items = _build_mev_marker_items(model_data, mev_data, monitoring_point, theme_value)

    summary_rows = []
    if threshold_items:
        summary_rows.append(html.Div(threshold_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-thresholds"))
    if marker_items:
        summary_rows.append(html.Div(marker_items, className="pd-mev-monitoring-summary-row pd-mev-monitoring-summary-row-markers"))

    if not summary_rows:
        return None
    return html.Div(summary_rows, className="pd-mev-monitoring-summary", **{"aria-label": "Monitoring summary"})


def _mev_rag_sort_weight(rag: str) -> int:
    return {"Red": 0, "Amber": 1, "Green": 2}.get(rag, 3)


def _build_mev_rag_tag_list(mev_rags: list[dict]):
    if not mev_rags:
        return html.Div(html.Span("No MEVs in scope", className="pd-mev-rag-tag pd-mev-rag-tag-neutral"), className="pd-mev-rag-tags")

    tone_map = {"Green": "green", "Amber": "amber", "Red": "red"}
    tags = []
    for entry in mev_rags:
        tone = tone_map.get(entry["rag"], "neutral")
        title = f"{entry['name']}: {entry['rag']}"
        tags.append(html.Span(entry["name"], className=f"pd-mev-rag-tag pd-mev-rag-tag-{tone}", title=title, **{"aria-label": title}))
    return html.Div(tags, className="pd-mev-rag-tags")


def _format_mev_quarter(value: str | None) -> str:
    """Format a development/quarter value as ``YYYYQn``."""
    if not value:
        return "—"
    return str(value).replace("-Q", "Q")


def _build_mev_rag_summary_card(selected_models: list[str], catalog: dict, monitoring_point: str | None) -> html.Article:
    summaries = []
    for model_name in selected_models:
        model_data = catalog.get(model_name, {})
        severe_quarter = iso_date_to_pd_quarter(model_data.get("severe_scenario_date"))
        mev_rags = []
        for mev_name, mev_data in (model_data.get("mevs") or {}).items():
            rag = calculate_pd_mev_worst_rag_after_quarter(mev_data, severe_quarter)
            mev_rags.append({"name": mev_name, "rag": rag})
        mev_rags.sort(key=lambda entry: (_mev_rag_sort_weight(entry["rag"]), entry["name"]))
        summaries.append({
            "model_name": model_name,
            "severe_quarter": severe_quarter,
            "development_dates": get_pd_mev_model_development_dates(model_data),
            "mev_rags": mev_rags,
        })

    if summaries:
        summary_children = [
            html.Div(
                className="pd-mev-rag-model",
                children=[
                    html.Div(html.Strong(summary["model_name"]), className="pd-mev-rag-model-header"),
                    html.Div(
                        className="pd-mev-rag-model-details",
                        children=[
                            html.Span(f"Scenario window starts: {_format_mev_quarter(summary['severe_quarter']) if summary['severe_quarter'] else (monitoring_point or 'Unavailable')}", className="pd-mev-rag-model-meta"),
                            html.Span(
                                "Development date: "
                                + (" / ".join(_format_mev_quarter(d) for d in summary["development_dates"]) if summary["development_dates"] else "—"),
                                className="pd-mev-rag-model-meta",
                            ),
                        ],
                    ),
                    _build_mev_rag_tag_list(summary["mev_rags"]),
                ],
            )
            for summary in summaries
        ]
    else:
        summary_children = [html.Div("No PD models are currently in scope for MEV evaluation.", className="pd-test-meta")]

    return html.Article(
        className="pd-test-card pd-mev-rag-summary-card",
        children=[
            html.Div(
                className="pd-test-card-heading",
                children=[html.Div([html.Span("Post-scenario RAG"), html.Div(html.H4("MEV RAG by model"), className="pd-card-title-row")])],
            ),
            html.Div(monitoring_point or "—", className="pd-test-value"),
            html.Div(f"Evaluation window: monitoring point onward", className="pd-test-meta"),
            html.Div("Method: each MEV is colored by its worst observed post-scenario RAG", className="pd-test-meta"),
            html.Div(summary_children, className="pd-mev-rag-summary-list"),
        ],
    )


def _build_mev_development_dates_card(selected_models: list[str], catalog: dict) -> html.Article:
    model_dates = [{"model_name": m, "dates": get_pd_mev_model_development_dates(catalog.get(m, {}))} for m in selected_models]
    distinct_count = len({d for item in model_dates for d in item["dates"]})

    if model_dates:
        rows = [
            html.Div(
                className="pd-mev-development-row",
                children=[
                    html.Strong(item["model_name"]),
                    html.Span(" / ".join(_format_mev_quarter(d) for d in item["dates"]) if item["dates"] else "—"),
                ],
            )
            for item in model_dates
        ]
    else:
        rows = [html.Div("No development dates in scope.", className="pd-test-meta")]

    return html.Article(
        className="pd-test-card pd-mev-development-card",
        children=[
            html.Div(
                className="pd-test-card-heading",
                children=[html.Div([html.Span("Reference"), html.Div(html.H4("Development dates"), className="pd-card-title-row")])],
            ),
            html.Div(rows, className="pd-mev-development-list"),
            html.Div(f"Distinct checkpoints: {distinct_count}", className="pd-test-meta"),
            html.Div("Purpose: Green range reference", className="pd-test-meta"),
        ],
    )


def _build_mev_filter_row(
    available_model_names: list[str],
    chart_model_names: list[str],
    mev_periods: list[str],
    range_store: dict,
    ctx: PdFilterContext,
) -> html.Div:
    selected_model_value = (
        "all"
        if (not available_model_names or len(chart_model_names) == len(available_model_names))
        else (chart_model_names[0] if chart_model_names else "all")
    )
    range_value = range_store.get("mev")
    has_mev_range_selection = bool((range_value or {}).get("from") or (range_value or {}).get("to"))
    has_model_selection = len(chart_model_names) != len(available_model_names)
    can_reset = has_model_selection or has_mev_range_selection

    model_options = [{"label": "All", "value": "all"}] + [{"label": m, "value": m} for m in available_model_names]

    return html.Div(
        className="pd-mev-filter-row",
        children=[
            html.Div(
                className="pd-mev-filter-copy",
                children=[
                    html.Div("Chart Filters", className="pd-content-kicker"),
                    html.P("Refine the MEV charts below by PD model."),
                ],
            ),
            html.Div(
                className="pd-mev-filter-controls",
                children=[
                    html.Div(
                        className="pd-mev-filter-group",
                        children=[
                            html.Label("PD Model"),
                            build_single_select_dropdown(
                                value_id=MEV_MODEL_FILTER_ID,
                                toggle_id=MEV_MODEL_TOGGLE_ID,
                                menu_id=MEV_MODEL_MENU_ID,
                                filter_key="mev-model",
                                options=model_options,
                                value=selected_model_value,
                                disabled=not available_model_names,
                            ),
                        ],
                    ),
                    *([build_range_controls("mev", mev_periods, range_value)] if mev_periods else []),
                    html.Div(
                        className="pd-mev-filter-actions",
                        children=[
                            html.Button("Reset chart filters", id=MEV_RESET_ID, className="btn pd-mev-filter-reset", disabled=not can_reset, n_clicks=0),
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 2.6 MEV Range (buildPdMevRangeSection)
# ---------------------------------------------------------------------------


def _build_mev_range_section(data: dict, ctx: PdFilterContext, range_store: dict, mev_filter_store: dict, theme_value: str | None = None) -> html.Section:
    catalog = data["mev_catalog"]
    mev_mnemonic_map = data.get("mev_mnemonic_map") or {}
    mev_description_map = data.get("mev_description_map") or {}
    selected_models = get_pd_mev_selected_models(catalog, ctx)

    chart_model_names = resolve_pd_mev_chart_model_names(selected_models, mev_filter_store.get("model"))
    available_mev_names = get_pd_mev_available_names_for_models(catalog, chart_model_names)
    chart_mev_names = resolve_pd_mev_chart_names(available_mev_names, mev_filter_store.get("names"))
    mev_periods = get_pd_mev_visible_periods(catalog, chart_model_names, chart_mev_names)

    total_mevs = sum(len((catalog.get(m, {}).get("mevs") or {})) for m in selected_models)
    severe_scenario_dates = [catalog.get(m, {}).get("severe_scenario_date") for m in selected_models]
    severe_scenario_dates = [d for d in severe_scenario_dates if d]
    model_scope_label = ", ".join(selected_models) if selected_models else "No models matched the current filters"

    model_panels = []
    for model_index, model_name in enumerate(chart_model_names):
        model_data = catalog.get(model_name, {})
        mev_entries = sorted(
            ((name, mdata) for name, mdata in (model_data.get("mevs") or {}).items() if name in chart_mev_names),
            key=lambda kv: kv[0],
        )
        if not mev_entries:
            continue

        current_quarter = _monitoring_point_to_mev_quarter(ctx.monitoring_point) if ctx.monitoring_point else None
        chart_cards = []
        for mev_index, (mev_name, mev_data) in enumerate(mev_entries):
            mev_mnemonic = mev_mnemonic_map.get(mev_name, mev_name)
            mev_description = mev_description_map.get(mev_name, "")
            thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
            chart_id = get_pd_mev_chart_id(model_name, mev_name)
            theme = normalize_theme_value(theme_value)
            trace_color = "#fb7185" if theme == "dark" else "#dc2626"
            fig = build_pd_mev_range_figure(model_data, mev_name, mev_data, trace_color, range_store.get("mev"), current_quarter=current_quarter, theme=theme)
            monitoring_summary = _build_mev_monitoring_summary(thresholds, model_data, mev_data, ctx.monitoring_point, theme_value)
            chart_cards.append(
                html.Article(
                    className="pd-mev-chart-card",
                    children=[
                        html.Div(
                            className="pd-mev-chart-header",
                            children=[
                                html.Div([
                                    html.Div(mev_name, className="pd-mev-chart-title"),
                                    html.Div(f"{mev_mnemonic}: {mev_description}" if mev_description else mev_mnemonic, className="pd-mev-chart-meta"),
                                ]),
                            ],
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
                                className="pd-mev-model-badges",
                                children=[
                                    html.Span(f"{len(mev_entries)} MEVs", className="pd-mev-model-badge"),
                                    html.Span(f"Severe scenario: {format_pd_short_date(model_data.get('severe_scenario_date'))}", className="pd-mev-model-badge"),
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
            html.Div("No MEV charts match the current chart filters", className="pd-mev-chart-title"),
            html.P(
                "Adjust the PD model selector or MEV checkboxes below the summary cards, or broaden the dashboard filters above.",
                className="pd-section-subtitle",
            ),
        ],
    )

    body = model_panels if (chart_model_names and chart_mev_names and model_panels) else [empty_state]

    return html.Section(
        id="pd-mev-range",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.6 MEV Range",
                "MEV Range",
                "Plot the selected PD models against their development green range, amber two-standard-deviation "
                "buffers, and red out-of-range zones.",
                "N/A",
                options={"show_rag": False},
            ),
            html.Div(
                className="pd-performance-note",
                children=[
                    "Each chart uses the model-specific development min/max as the green band, extends amber by "
                    "two standard deviations beyond that development range, and marks the model development date "
                    "and severe scenario date directly on the timeline. Source: ",
                    html.Strong(data.get("mev_source_file") or "dummy_mev_data.xlsx"),
                    ".",
                ],
            ),
            html.Div(
                className="pd-test-grid pd-mev-summary-grid",
                children=[
                    _build_mev_rag_summary_card(selected_models, catalog, ctx.monitoring_point),
                    build_pd_static_info_card(
                        "Models in scope",
                        f"{len(selected_models)}",
                        [
                            {"label": "Segment filter", "value": "All segments" if ctx.segment == "all" else ctx.segment},
                            {"label": "Model scope", "value": model_scope_label},
                        ],
                        options={"test_label": "Filters"},
                    ),
                    build_pd_static_info_card(
                        "MEV charts",
                        f"{total_mevs}",
                        [
                            {"label": "Rendered panels", "value": f"{total_mevs} charts" if total_mevs else "No charts in scope"},
                            {"label": "Catalog models", "value": f"{len(catalog)}"},
                        ],
                        options={"test_label": "Coverage"},
                    ),
                    _build_mev_development_dates_card(selected_models, catalog),
                    build_pd_static_info_card(
                        "Severe scenario",
                        format_pd_date_summary(severe_scenario_dates),
                        [
                            {"label": "Distinct checkpoints", "value": f"{len(set(severe_scenario_dates))}"},
                            {"label": "Purpose", "value": "Scenario marker"},
                        ],
                        options={"test_label": "Scenario"},
                    ),
                ],
            ),
            _build_mev_filter_row(selected_models, chart_model_names, mev_periods, range_store, ctx),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# Main render function (renderPdModels)
# ---------------------------------------------------------------------------


def render_pd_performance_content(data: dict, ctx: PdFilterContext, range_store: dict, trend_horizon_store: dict, mev_filter_store: dict, theme_value: str | None = None) -> list:
    observations = data["performance_observations"]
    rating_observations = data["rating_migration_observations"]
    monitoring_thresholds = data["monitoring_thresholds"]
    performance_horizons = data["performance_horizons"]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    crr_scale = get_pd_crr_master_scale(monitoring_thresholds)

    cq = ctx.monitoring_point
    pq = get_previous_pd_quarter(cq)

    context = get_pd_performance_context(performance_horizons, ctx)
    current_rows = filter_pd_performance_observations(observations, context["snapshot_quarter"], ctx)

    availability_note = None
    if not current_rows:
        availability_note = html.Div(
            f"No PD observations are available for snapshot date {context['snapshot_quarter']} using {context['predicted_column']}.",
            className="pd-performance-note pd-data-note",
        )

    current_rag_values = calculate_pd_rag_metrics(observations, rating_observations, context["snapshot_quarter"], ctx, crr_scale)
    previous_rag_values = calculate_pd_rag_metrics(observations, rating_observations, context["previous_quarter"], ctx, crr_scale)

    def group_rag(group: str) -> str:
        return get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, current_rag_values[metric])
            for metric in config.PD_RAG_GROUPS[group]
        ])

    calibration_trend_horizon_key = _trend_horizon_value(trend_horizon_store, "calibration")
    calibration_trend_context = get_pd_performance_context_for_horizon(performance_horizons, calibration_trend_horizon_key, ctx)
    calibration_trend_periods = get_pd_range_periods(ctx.quarters, calibration_trend_context["snapshot_quarter"])

    go_live_horizon_key = "1y"
    go_live_context = get_pd_performance_context_for_horizon(performance_horizons, go_live_horizon_key, ctx)
    go_live_start = get_pd_go_live_quarter(observations, go_live_horizon_key, ctx)
    go_live_periods = [
        period for period in get_pd_range_periods(ctx.quarters, go_live_context["snapshot_quarter"])
        if not go_live_start or period >= go_live_start
    ]

    discrimination_trend_horizon_key = _trend_horizon_value(trend_horizon_store, "discrimination")
    discrimination_trend_context = get_pd_performance_context_for_horizon(performance_horizons, discrimination_trend_horizon_key, ctx)
    discrimination_trend_periods = get_pd_range_periods(ctx.quarters, discrimination_trend_context["snapshot_quarter"])

    balance_sheet_context = get_pd_performance_context_for_horizon(performance_horizons, "nco_1y", ctx)
    balance_sheet_periods = get_pd_range_periods(ctx.quarters, balance_sheet_context["snapshot_quarter"])

    balance_sheet_values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx, crr_scale)
    previous_balance_sheet_values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, balance_sheet_context["previous_quarter"], "nco_1y", ctx, crr_scale)

    balance_sheet_notching = calculate_pd_notching_components(
        filter_pd_performance_observations_for_horizon(observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx), crr_scale,
    )
    previous_balance_sheet_notching = calculate_pd_notching_components(
        filter_pd_performance_observations_for_horizon(observations, balance_sheet_context["previous_quarter"], "nco_1y", ctx), crr_scale,
    )

    balance_sheet_assignment_rag = calculate_pd_calibration_assignment_rag(
        balance_sheet_values["Confidence Interval Test"], balance_sheet_notching["signed_difference"], monitoring_thresholds,
    )
    previous_balance_sheet_assignment_rag = calculate_pd_calibration_assignment_rag(
        previous_balance_sheet_values["Confidence Interval Test"], previous_balance_sheet_notching["signed_difference"], monitoring_thresholds,
    )

    if balance_sheet_assignment_rag == "N/A":
        balance_sheet_rag = get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, balance_sheet_values[metric]) for metric in config.PD_RAG_GROUPS["calibration"]
        ])
    else:
        balance_sheet_rag = balance_sheet_assignment_rag

    if previous_balance_sheet_assignment_rag == "N/A":
        previous_balance_sheet_rag = get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, previous_balance_sheet_values[metric]) for metric in config.PD_RAG_GROUPS["calibration"]
        ])
    else:
        previous_balance_sheet_rag = previous_balance_sheet_assignment_rag

    balance_sheet_confidence_rag = calculate_pd_metric_rag(thresholds, "Confidence Interval Test", balance_sheet_values["Confidence Interval Test"])
    balance_sheet_notching_rag = calculate_pd_metric_rag(thresholds, "Notching Test", balance_sheet_values["Notching Test"])
    balance_sheet_assignment_tooltip = build_pd_calibration_assignment_tooltip(
        "Balance Sheet 1 year",
        balance_sheet_values["Confidence Interval Test"],
        balance_sheet_notching["signed_difference"],
        balance_sheet_assignment_rag,
        balance_sheet_rag,
        balance_sheet_confidence_rag,
        balance_sheet_notching_rag,
    )

    balance_sheet_availability_note = None
    if not filter_pd_performance_observations_for_horizon(observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx):
        balance_sheet_availability_note = html.Div(
            f"No PD observations are available for snapshot date {balance_sheet_context['snapshot_quarter']} using {balance_sheet_context['predicted_column']}.",
            className="pd-performance-note pd-data-note",
        )

    current_monitoring_ead = calculate_pd_ead_summaries(observations, cq, ctx)
    previous_monitoring_ead = calculate_pd_ead_summaries(observations, pq, ctx)

    previous_calibration_assignment_details = calculate_pd_calibration_conservatism_details(observations, rating_observations, pq, ctx, crr_scale, monitoring_thresholds)
    calibration_assignment_details = calculate_pd_calibration_conservatism_details(observations, rating_observations, cq, ctx, crr_scale, monitoring_thresholds)

    calibration_assignment_rag = calibration_assignment_details["rag"]
    calibration_rag = group_rag("calibration") if calibration_assignment_rag == "N/A" else calibration_assignment_rag

    if previous_calibration_assignment_details["rag"] == "N/A":
        previous_calibration_rag = get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, previous_rag_values[metric]) for metric in config.PD_RAG_GROUPS["calibration"]
        ])
    else:
        previous_calibration_rag = previous_calibration_assignment_details["rag"]

    discrimination_default_count = calculate_pd_default_count_for_horizon(observations, context["snapshot_quarter"], "1y", ctx)
    previous_discrimination_default_count = calculate_pd_default_count_for_horizon(observations, context["previous_quarter"], "1y", ctx)
    discrimination_rag = calculate_pd_discrimination_section_rag(thresholds, current_rag_values, discrimination_default_count)
    previous_discrimination_rag = calculate_pd_discrimination_section_rag(thresholds, previous_rag_values, previous_discrimination_default_count)
    discrimination_rag_tooltip = (
        "If the 1-year default count is below 15, the RAG is forced to Amber. "
        "Otherwise: if Delta Accuracy Ratio is Red and Accuracy Ratio is Green, the RAG is "
        "Amber. If Delta Accuracy Ratio is Red and Accuracy Ratio is Amber, the RAG is Red. "
        "Otherwise the Accuracy Ratio RAG is used."
    )
    accuracy_ratio_rag = calculate_pd_metric_rag(thresholds, "Accuracy Ratio", current_rag_values["Accuracy Ratio"])
    delta_accuracy_ratio_rag = calculate_pd_metric_rag(thresholds, "Delta Accuracy Ratio", current_rag_values["Delta Accuracy Ratio"])

    # -- 1.2 calibration horizon cards (summary card + 1y/2y EAD/RAG/test cards) --
    calibration_horizon_cards = [
        build_pd_section_rag_card(
            "Calibration Conservatism RAG (ECL PIT)",
            calibration_rag,
            previous_calibration_rag,
            context,
            options={
                "card_title": "Calibration Conservatism RAG (ECL PIT)",
                "extra_class": "pd-calibration-summary-card",
                "tooltip": build_pd_calibration_tooltip(calibration_assignment_details),
                "hide_status": True,
                "meta_label": "Monitoring point",
                "meta_value": context["monitoring_point"],
                "hide_comparison": True,
            },
        ),
    ]

    calibration_overview = {}
    for horizon_key, suffix in (("1y", "1 year"), ("2y", "2 year")):
        horizon_context = get_pd_performance_context_for_horizon(performance_horizons, horizon_key, ctx)
        horizon_values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, horizon_context["snapshot_quarter"], horizon_key, ctx, crr_scale)
        previous_horizon_values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, horizon_context["previous_quarter"], horizon_key, ctx, crr_scale)
        horizon_notching = calculate_pd_notching_components(
            filter_pd_performance_observations_for_horizon(observations, horizon_context["snapshot_quarter"], horizon_key, ctx), crr_scale,
        )
        previous_horizon_notching = calculate_pd_notching_components(
            filter_pd_performance_observations_for_horizon(observations, horizon_context["previous_quarter"], horizon_key, ctx), crr_scale,
        )
        horizon_assignment_rag = calculate_pd_calibration_assignment_rag(horizon_values["Confidence Interval Test"], horizon_notching["signed_difference"], monitoring_thresholds)
        previous_horizon_assignment_rag = calculate_pd_calibration_assignment_rag(previous_horizon_values["Confidence Interval Test"], previous_horizon_notching["signed_difference"], monitoring_thresholds)

        if horizon_assignment_rag == "N/A":
            horizon_calibration_rag = get_worst_pd_rag([
                calculate_pd_metric_rag(thresholds, metric, horizon_values[metric]) for metric in config.PD_RAG_GROUPS["calibration"]
            ])
        else:
            horizon_calibration_rag = horizon_assignment_rag

        if previous_horizon_assignment_rag == "N/A":
            previous_horizon_calibration_rag = get_worst_pd_rag([
                calculate_pd_metric_rag(thresholds, metric, previous_horizon_values[metric]) for metric in config.PD_RAG_GROUPS["calibration"]
            ])
        else:
            previous_horizon_calibration_rag = previous_horizon_assignment_rag

        horizon_confidence_rag = calculate_pd_metric_rag(thresholds, "Confidence Interval Test", horizon_values["Confidence Interval Test"])
        horizon_notching_rag = calculate_pd_metric_rag(thresholds, "Notching Test", horizon_values["Notching Test"])
        horizon_assignment_tooltip = build_pd_calibration_assignment_tooltip(
            suffix,
            horizon_values["Confidence Interval Test"],
            horizon_notching["signed_difference"],
            horizon_assignment_rag,
            horizon_calibration_rag,
            horizon_confidence_rag,
            horizon_notching_rag,
        )

        current_horizon_ead = current_monitoring_ead.get(horizon_key) or {"ead": None, "share": None, "combined_ead": None}
        previous_horizon_ead = previous_monitoring_ead.get(horizon_key) or {"ead": None, "share": None, "combined_ead": None}

        calibration_overview[horizon_key] = {
            "notching_value": horizon_values["Notching Test"],
            "notching_rag": horizon_notching_rag,
            "confidence_value": horizon_values["Confidence Interval Test"],
            "confidence_rag": horizon_confidence_rag,
            "assignment_rag": horizon_calibration_rag,
            "assignment_tooltip": horizon_assignment_tooltip,
        }

        calibration_horizon_cards.extend([
            build_pd_ead_card(
                current_horizon_ead, previous_horizon_ead, horizon_context,
                options={
                    "card_title": f"EAD {suffix}",
                    "current_label": horizon_context["snapshot_quarter"],
                    "previous_label": horizon_context["previous_quarter"] or "No prior quarter",
                },
            ),
            build_pd_section_rag_card(
                "RAG Assignment", horizon_calibration_rag, previous_horizon_calibration_rag, horizon_context,
                options={"card_title": f"RAG Assignment {suffix}", "tooltip": horizon_assignment_tooltip, "hide_status": True},
            ),
            build_pd_test_card(
                "Notching Test", horizon_values, previous_horizon_values, thresholds, horizon_context,
                options={"card_title": f"Notching Test {suffix}", "format": "count"},
            ),
            build_pd_test_card(
                "Confidence Interval Test", horizon_values, previous_horizon_values, thresholds, horizon_context,
                options={"card_title": f"Confidence Interval {suffix}", "format": "percent"},
            ),
        ])

    performance_pd_overview = calculate_pd_overview_performance_rag(calibration_rag, discrimination_rag, balance_sheet_rag)
    overview_status_note = build_pd_overview_performance_rag_tooltip(calibration_rag, discrimination_rag, balance_sheet_rag, performance_pd_overview)
    performance_pd_overview = {**performance_pd_overview, "tooltip": overview_status_note}

    # -----------------------------------------------------------------
    # 1.1 Overview - "RAG Assignment Overview" process-flow diagram
    # (port of buildPdOverviewHeatmap)
    # -----------------------------------------------------------------
    overview = {
        "calibration": {
            "overall_rag": calibration_rag,
            "tooltip": build_pd_calibration_tooltip(calibration_assignment_details),
            "one_year": calibration_overview.get("1y", {}),
            "two_year": calibration_overview.get("2y", {}),
        },
        "discrimination": {
            "overall_rag": discrimination_rag,
            "tooltip": discrimination_rag_tooltip,
            "accuracy_value": current_rag_values["Accuracy Ratio"],
            "accuracy_rag": accuracy_ratio_rag,
            "delta_value": current_rag_values["Delta Accuracy Ratio"],
            "delta_rag": delta_accuracy_ratio_rag,
        },
        "balance_sheet": {
            "overall_rag": balance_sheet_rag,
            "assignment_tooltip": balance_sheet_assignment_tooltip,
            "notching_value": balance_sheet_values["Notching Test"],
            "notching_rag": balance_sheet_notching_rag,
            "confidence_value": balance_sheet_values["Confidence Interval Test"],
            "confidence_rag": balance_sheet_confidence_rag,
        },
        "performance_pd": performance_pd_overview,
    }

    overview_section = html.Section(
        id="pd-analysis-scope",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("1.1 Overview", className="pd-content-kicker"),
                    html.H3("RAG Assignment Overview"),
                    html.P(
                        "At-a-glance summary of the current ECL PIT PD and Balance Sheet PD calibration and "
                        "discriminatory power diagnostics."
                    ),
                ],
            ),
            build_pd_overview_heatmap(overview),
            *([availability_note] if availability_note is not None else []),
        ],
    )

    # -----------------------------------------------------------------
    # 1.2 ECL PIT PD - Calibration Conservatism
    # -----------------------------------------------------------------
    calibration_performance_trend = build_pd_performance_trend_for_horizon(
        observations, rating_observations, calibration_trend_context["snapshot_quarter"], calibration_trend_horizon_key, ctx, crr_scale,
    )
    calibration_rag_trend = build_pd_calibration_rag_trend(observations, rating_observations, cq, ctx, crr_scale, monitoring_thresholds)

    section_1_2 = html.Section(
        id="pd-calibration-rag",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 ECL PIT PD - Calibration Conservatism",
                "ECL PIT PD - Calibration Conservatism",
                "Compare observed defaults with predicted PIT PD, and review monotonicity across rating grades for "
                "the ECL monitoring population.",
                calibration_rag,
                options={"show_rag": False},
            ),
            html.Div(className="pd-test-grid pd-calibration-test-grid", children=calibration_horizon_cards),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
                    html.Div(
                        id="pd-calibration-rag-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Calibration Conservatism RAG (ECL PIT) Trend",
                                "Quarter-by-quarter Calibration Conservatism RAG (ECL PIT) shown as a simple "
                                "color-coded dot timeline.",
                                "calibration_rag",
                                get_pd_range_periods(ctx.quarters, cq),
                                range_store.get("calibration_rag"),
                            ),
                            dcc.Graph(
                                id="pd-calibration-rag-trend-chart",
                                figure=build_pd_calibration_rag_trend_figure(calibration_rag_trend, cq, range_store.get("calibration_rag")),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                    html.Div(
                        id="pd-confidence-interval-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Confidence Interval Test Trend",
                                f"Confidence interval test trend using the {calibration_trend_context['horizon_label']} "
                                f"time horizon. Markers use RAG colors.",
                                "calibration_ci",
                                calibration_trend_periods,
                                range_store.get("calibration_ci"),
                                extra_controls=build_trend_horizon_control("calibration_ci", calibration_trend_horizon_key),
                            ),
                            dcc.Graph(
                                id="pd-confidence-interval-trend-chart",
                                figure=build_pd_confidence_interval_trend_figure(
                                    calibration_performance_trend, monitoring_thresholds, calibration_trend_context["snapshot_quarter"], range_store.get("calibration_ci"),
                                ),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="pd-notching-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Notching Trend",
                        f"Actual notch, predicted notch, and notching difference using the "
                        f"{calibration_trend_context['horizon_label']} time horizon.",
                        "calibration_notching",
                        calibration_trend_periods,
                        range_store.get("calibration_notching"),
                        extra_controls=build_trend_horizon_control("calibration_notching", calibration_trend_horizon_key),
                    ),
                    dcc.Graph(
                        id="pd-notching-trend-chart",
                        figure=build_pd_notching_trend_figure(calibration_performance_trend, monitoring_thresholds, range_store.get("calibration_notching")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-notching-trend-chart",
                    ),
                ],
            ),
            html.Div(
                id="pd-calibration-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Calibration Trend",
                        f"Actual vs. predicted default rates and their ratio using the "
                        f"{calibration_trend_context['horizon_label']} time horizon. Ratio trend markers use RAG colors.",
                        "calibration_default_rate",
                        calibration_trend_periods,
                        range_store.get("calibration_default_rate"),
                        extra_controls=build_trend_horizon_control("calibration_default_rate", calibration_trend_horizon_key),
                    ),
                    dcc.Graph(
                        id="pd-default-rate-trend-chart",
                        figure=build_pd_default_rate_trend_figure(calibration_performance_trend, monitoring_thresholds, range_store.get("calibration_default_rate")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-calibration-trend-chart",
                    ),
                ],
            ),
        ],
    )

    # -----------------------------------------------------------------
    # 1.3 ECL PIT PD - Discriminatory Power
    # -----------------------------------------------------------------
    discrimination_performance_trend = build_pd_performance_trend_for_horizon(
        observations, rating_observations, discrimination_trend_context["snapshot_quarter"], discrimination_trend_horizon_key, ctx, crr_scale,
    )
    discrimination_rag_trend = build_pd_discrimination_rag_trend(observations, rating_observations, cq, ctx, crr_scale, monitoring_thresholds)
    go_live_performance_trend = build_pd_performance_trend_for_horizon(
        observations, rating_observations, go_live_context["snapshot_quarter"], go_live_horizon_key, ctx, crr_scale,
    )
    discrimination_trend_figures = build_pd_discrimination_trend_figures(
        discrimination_performance_trend, monitoring_thresholds, discrimination_trend_context["snapshot_quarter"], range_store.get("discrimination_trend"),
    )

    section_1_3 = html.Section(
        id="pd-discrimination-rag",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.3 ECL PIT PD - Discriminatory Power",
                "ECL PIT PD - Discriminatory Power",
                "Assess how effectively PIT PD separates higher-risk and lower-risk observations within the "
                "monitored ECL population.",
                discrimination_rag,
                options={"show_rag": False},
            ),
            html.Div(
                className="pd-test-grid pd-discrimination-test-grid",
                children=[
                    build_pd_section_rag_card(
                        "Discriminatory Power RAG", discrimination_rag, previous_discrimination_rag, context,
                        options={
                            "card_title": "Discriminatory Power RAG",
                            "tooltip": discrimination_rag_tooltip,
                            "hide_status": True,
                            "meta_label": "Monitoring point",
                            "meta_value": context["monitoring_point"],
                            "extra_meta_rows": [{"label": "Default 1 year count", "value": fmt_n(discrimination_default_count)}],
                            "hide_comparison": True,
                        },
                    ),
                    build_pd_test_card(
                        "Accuracy Ratio", current_rag_values, previous_rag_values, thresholds, context,
                        options={"test_label": "Accuracy Ratio 1 year", "format": "ratio"},
                    ),
                    build_pd_test_card(
                        "Delta Accuracy Ratio", current_rag_values, previous_rag_values, thresholds, context,
                        options={
                            "card_title": "Delta Accuracy Ratio 1 year",
                            "format": "ratio",
                            "extra_meta_rows": [{"label": "Go-live date", "value": current_rag_values.get("Go Live Quarter") or "—"}],
                            "tooltip": (
                                f"Reference go-live quarter: {current_rag_values['Go Live Quarter']}"
                                if current_rag_values.get("Go Live Quarter")
                                else "No go-live quarter between 2019Q2 and 2019Q4 is available for the selected filters."
                            ),
                        },
                    ),
                ],
            ),
            html.Div(
                id="pd-discrimination-rag-trend-panel",
                className="section-card pd-discrimination-trend-section",
                children=[
                    build_chart_header(
                        "Discriminatory Power RAG Trend",
                        "Quarter-by-quarter Discriminatory Power RAG shown as a simple color-coded dot timeline.",
                        "discrimination_rag",
                        get_pd_range_periods(ctx.quarters, cq),
                        range_store.get("discrimination_rag"),
                    ),
                    dcc.Graph(
                        id="pd-discrimination-rag-trend-chart",
                        figure=build_pd_discrimination_rag_trend_figure(discrimination_rag_trend, cq, range_store.get("discrimination_rag")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact",
                    ),
                ],
            ),
            html.Div(
                id="pd-go-live-accuracy-trend-panel",
                className="section-card pd-discrimination-trend-section",
                children=[
                    build_chart_header(
                        "Accuracy Ratio and Go-Live Delta Trend",
                        f"Accuracy Ratio, Go Live Accuracy Ratio, and Delta Accuracy Ratio from "
                        f"{go_live_start or 'the configured go-live period'} onward. PD horizon is fixed to the "
                        f"{go_live_context['horizon_label']} time horizon and delta markers use threshold shading.",
                        "discrimination_accuracy",
                        go_live_periods,
                        range_store.get("discrimination_accuracy"),
                        extra_controls=build_frozen_horizon_control("Accuracy trend PD horizon"),
                    ),
                    dcc.Graph(
                        id="pd-go-live-accuracy-trend-chart",
                        figure=build_pd_go_live_accuracy_trend_figure(go_live_performance_trend, monitoring_thresholds, go_live_start, range_store.get("discrimination_accuracy")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-go-live-accuracy-trend-chart",
                    ),
                ],
            ),
            html.Div(
                id="pd-discrimination-trend-panel",
                className="section-card pd-discrimination-trend-section",
                children=[
                    build_chart_header(
                        "Discriminatory Power Trend Other Metrics Trend",
                        f"Gini Coefficient, KS Statistic, and Kendall's Tau through "
                        f"{discrimination_trend_context['snapshot_quarter']} using the "
                        f"{discrimination_trend_context['horizon_label']} time horizon. Markers use RAG colors.",
                        "discrimination_trend",
                        discrimination_trend_periods,
                        range_store.get("discrimination_trend"),
                        extra_controls=build_trend_horizon_control("discrimination_trend", discrimination_trend_horizon_key),
                    ),
                    html.Div(
                        id="pd-discrimination-trend-grid",
                        className="pd-discrimination-trend-grid",
                        children=[
                            dcc.Graph(id="pd-discrimination-trend-gini-coefficient", figure=discrimination_trend_figures["gini_coefficient"], config=_GRAPH_CONFIG, className="pd-discrimination-trend-chart"),
                            dcc.Graph(id="pd-discrimination-trend-ks-statistic", figure=discrimination_trend_figures["ks_statistic"], config=_GRAPH_CONFIG, className="pd-discrimination-trend-chart"),
                            dcc.Graph(id="pd-discrimination-trend-kendall-tau", figure=discrimination_trend_figures["kendall_tau"], config=_GRAPH_CONFIG, className="pd-discrimination-trend-chart"),
                        ],
                    ),
                ],
            ),
        ],
    )

    # -----------------------------------------------------------------
    # 1.4 Balance Sheet PD - Calibration Conservatism
    # -----------------------------------------------------------------
    balance_sheet_performance_trend = build_pd_performance_trend_for_horizon(
        observations, rating_observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx, crr_scale,
    )
    balance_sheet_rag_trend = build_pd_balance_sheet_calibration_rag_trend(
        observations, rating_observations, balance_sheet_context["snapshot_quarter"], ctx, crr_scale, monitoring_thresholds,
    )

    section_1_4 = html.Section(
        id="pd-balance-sheet-calibration",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.4 Balance Sheet PD - Calibration Conservatism",
                "Balance Sheet PD - Calibration Conservatism",
                "Assess balance sheet PD calibration with the same framework, using CPD NCO as the predicted PD "
                "input for the 1-year horizon.",
                "N/A",
                options={"show_rag": False},
            ),
            html.Div(
                className="pd-performance-note",
                children=[
                    "Balance sheet calibration uses the same card logic as ECL PIT calibration, but evaluates the "
                    "1-year population with ",
                    html.Strong(balance_sheet_context["predicted_column"]),
                    " as the predicted PD source.",
                ],
            ),
            *([balance_sheet_availability_note] if balance_sheet_availability_note is not None else []),
            html.Div(
                className="pd-test-grid pd-test-grid-3",
                children=[
                    build_pd_section_rag_card(
                        "RAG Assignment", balance_sheet_rag, previous_balance_sheet_rag, balance_sheet_context,
                        options={"card_title": "Calibration Conservatism RAG", "tooltip": balance_sheet_assignment_tooltip, "hide_status": True},
                    ),
                    build_pd_test_card(
                        "Notching Test", balance_sheet_values, previous_balance_sheet_values, thresholds, balance_sheet_context,
                        options={"card_title": "Notching Test 1 year", "format": "count"},
                    ),
                    build_pd_test_card(
                        "Confidence Interval Test", balance_sheet_values, previous_balance_sheet_values, thresholds, balance_sheet_context,
                        options={"card_title": "Confidence Interval 1 year", "format": "percent"},
                    ),
                ],
            ),
            html.Div(
                className="pd-trend-detail-grid",
                children=[
                    html.Div(
                        id="pd-balance-sheet-calibration-rag-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Balance Sheet Calibration Conservatism RAG Trend",
                                "Quarter-by-quarter Calibration Conservatism RAG shown as a simple color-coded dot timeline.",
                                "balance_sheet_calibration_rag",
                                balance_sheet_periods,
                                range_store.get("balance_sheet_calibration_rag"),
                                extra_controls=build_frozen_horizon_control("Balance sheet calibration RAG PD horizon"),
                            ),
                            dcc.Graph(
                                id="pd-balance-sheet-calibration-rag-trend-chart",
                                figure=build_pd_balance_sheet_calibration_rag_trend_figure(balance_sheet_rag_trend, balance_sheet_context["snapshot_quarter"], range_store.get("balance_sheet_calibration_rag")),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
                            ),
                        ],
                    ),
                    html.Div(
                        id="pd-balance-sheet-confidence-interval-trend-panel",
                        className="section-card pd-default-rate-trend-section",
                        children=[
                            build_chart_header(
                                "Balance Sheet Confidence Interval Test Trend",
                                f"Confidence interval test trend using {balance_sheet_context['predicted_column']} "
                                f"for the fixed {balance_sheet_context['horizon_label']} horizon. Markers use RAG colors.",
                                "balance_sheet_ci",
                                balance_sheet_periods,
                                range_store.get("balance_sheet_ci"),
                                extra_controls=build_frozen_horizon_control("Balance sheet calibration PD horizon"),
                            ),
                            dcc.Graph(
                                id="pd-balance-sheet-confidence-interval-trend-chart",
                                figure=build_pd_confidence_interval_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, balance_sheet_context["snapshot_quarter"], range_store.get("balance_sheet_ci")),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="pd-balance-sheet-notching-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Balance Sheet Notching Trend",
                        f"Actual notch, predicted notch, and notching difference using "
                        f"{balance_sheet_context['predicted_column']} for the fixed {balance_sheet_context['horizon_label']} horizon.",
                        "balance_sheet_notching",
                        balance_sheet_periods,
                        range_store.get("balance_sheet_notching"),
                        extra_controls=build_frozen_horizon_control("Balance sheet calibration PD horizon"),
                    ),
                    dcc.Graph(
                        id="pd-balance-sheet-notching-trend-chart",
                        figure=build_pd_notching_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, range_store.get("balance_sheet_notching")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-notching-trend-chart",
                    ),
                ],
            ),
            html.Div(
                id="pd-balance-sheet-calibration-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Balance Sheet Calibration Trend",
                        f"Actual vs. predicted default rates and their ratio using "
                        f"{balance_sheet_context['predicted_column']} for the fixed {balance_sheet_context['horizon_label']} "
                        f"horizon. Ratio trend markers use RAG colors.",
                        "balance_sheet_default_rate",
                        balance_sheet_periods,
                        range_store.get("balance_sheet_default_rate"),
                        extra_controls=build_frozen_horizon_control("Balance sheet calibration PD horizon"),
                    ),
                    dcc.Graph(
                        id="pd-balance-sheet-default-rate-trend-chart",
                        figure=build_pd_default_rate_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, range_store.get("balance_sheet_default_rate")),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-calibration-trend-chart",
                    ),
                ],
            ),
        ],
    )

    # -----------------------------------------------------------------
    # Chapter wrappers + chapter 2 (Post Subjective Review Analysis)
    # -----------------------------------------------------------------
    chapter_1 = html.Section(
        id="pd-rag-assignment",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "1.",
                "RAG Assignment",
                "Core monitoring view for PD model health, combining the current overview with ECL PIT PD and "
                "Balance Sheet PD calibration and discriminatory-power diagnostics.",
                options={"note": f"Monitoring point {cq}"},
            ),
        ],
    )
    chapter_1_body = html.Div(className="pd-chapter-body pd-chapter-body-primary", children=[overview_section, section_1_2, section_1_3, section_1_4])

    chapter_2 = html.Section(
        id="pd-post-subjective-review-analysis",
        className="pd-content-section pd-chapter-section",
        children=[
            build_pd_chapter_heading(
                "2.",
                "Post Subjective Review Analysis",
                "This section presents a qualitative assessment with a binary outcome, such as whether rank "
                "ordering is maintained. While no standalone RAG is assigned to this analysis, any material "
                "concerns identified through the deep-dive review will be highlighted in the monitoring report and "
                "reflected in the overall Model RAG.",
                options={"note": "Scaffold aligned to requested subsections"},
            ),
        ],
    )

    section_2_1 = html.Section(
        id="pd-post-subjective-overview",
        className="pd-content-section pd-placeholder-section",
        children=[
            build_pd_section_heading(
                "2.1 Overview", "Overview",
                "High-level landing area for the future post subjective review analysis package.",
                "N/A", options={"show_rag": False},
            ),
            _build_placeholder_card(
                "Post Subjective Review Overview",
                "This placeholder section is ready for the future summary narrative, key flags, and cross-check "
                "metrics that will frame the post subjective review analysis.",
                ["Summary KPIs", "Narrative insights", "Reviewer actions"],
            ),
        ],
    )

    section_2_2 = html.Section(
        id="pd-transition-matrix-distance",
        className="pd-content-section pd-placeholder-section",
        children=[
            build_pd_section_heading(
                "2.2 Transition Matrix", "Transition Matrix",
                "Future section for comparing post-review transition behavior against the reference migration structure.",
                "N/A", options={"show_rag": False},
            ),
            _build_placeholder_card(
                "Transition Matrix",
                "A compact placeholder is in place for the transition matrix views, distance metrics, and "
                "interpretation rules that will be added later.",
                ["Transition view", "Distance metric", "Threshold guidance"],
            ),
        ],
    )

    section_2_3 = html.Section(
        id="pd-population-stability-index",
        className="pd-content-section pd-placeholder-section",
        children=[
            build_pd_section_heading(
                "2.3 PSI", "PSI",
                "Future section for population stability diagnostics after subjective review adjustments.",
                "N/A", options={"show_rag": False},
            ),
            _build_placeholder_card(
                "Population Stability Index (PSI)",
                "This placeholder reserves space for PSI trends, distribution shift diagnostics, and any future "
                "threshold-based alerts.",
                ["PSI trend", "Shift diagnostics", "Threshold alerts"],
            ),
        ],
    )

    section_2_4 = _build_rank_ordering_section(data, ctx, range_store)

    section_2_5 = html.Section(
        id="pd-sensitivity-analysis",
        className="pd-content-section pd-placeholder-section",
        children=[
            build_pd_section_heading(
                "2.5 Sensitivity Analysis", "Sensitivity Analysis",
                "Future section for showing how model outputs react to selected drivers and review overlays.",
                "N/A", options={"show_rag": False},
            ),
            _build_placeholder_card(
                "Sensitivity Analysis",
                "A lightweight placeholder is ready for future parameter sensitivities, comparative views, and "
                "documented interpretation logic.",
                ["Driver impact", "Scenario comparison", "Review commentary"],
            ),
        ],
    )

    section_2_6 = _build_mev_range_section(data, ctx, range_store, mev_filter_store, theme_value=theme_value)

    chapter_2_body = html.Div(
        className="pd-chapter-body pd-chapter-body-secondary",
        children=[section_2_1, section_2_2, section_2_3, section_2_4, section_2_5, section_2_6],
    )

    return [chapter_1, chapter_1_body, chapter_2, chapter_2_body]


# ---------------------------------------------------------------------------
# Default filter context + top-level layout
# ---------------------------------------------------------------------------


def default_filter_context(data: dict) -> PdFilterContext:
    quarters = data["quarters"]
    latest_quarter = data.get("latest_quarter") or (sorted(quarters)[-1] if quarters else "")
    return PdFilterContext(
        quarters=quarters,
        models=set(data["model_names"]),
        segment="all",
        monitoring_point=latest_quarter,
    )


def _build_top_bar(data: dict) -> html.Div:
    return html.Div(
        className="top-bar",
        children=[
            html.Div(
                style={"flex": "1"},
                children=[
                    html.Div(
                        "Wholesale Portfolio Model Monitoring Dashboard",
                        className="monitoring-dashboard-title",
                    ),
                    build_global_filters(data),
                ],
            ),
        ],
    )


def build_stores() -> list:
    """``dcc.Store`` components backing this page's filter/range state.

    Rendered once in the shared app shell (:func:`shell.build_app_shell`) so
    they persist while navigating between pages.
    """
    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=TREND_HORIZON_STORE_ID, data=dict(DEFAULT_TREND_HORIZON_STORE)),
        dcc.Store(id=MEV_FILTER_STORE_ID, data=dict(DEFAULT_MEV_FILTER_STORE)),
    ]


def build_layout() -> list:
    """Registry entry point: build the page from the loaded dashboard data."""
    from ...data_access import PD_PERFORMANCE_DATA

    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Top bar + main content for the PD Performance page."""
    ctx = default_filter_context(data)
    return [
        _build_top_bar(data),
        html.Div(
            className="content",
            children=[
                html.Div(
                    id="tab-pd_models",
                    className="tab-panel active pd-performance-app",
                    children=[
                        html.Div(
                            id=CONTENT_ID,
                            children=render_pd_performance_content(
                                data,
                                ctx,
                                {},
                                dict(DEFAULT_TREND_HORIZON_STORE),
                                dict(DEFAULT_MEV_FILTER_STORE),
                            ),
                        ),
                    ],
                ),
            ],
        ),
    ]
