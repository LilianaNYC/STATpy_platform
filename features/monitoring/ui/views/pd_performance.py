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

import math

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
    build_pd_psi_trend_figure,
    build_pd_transition_combined_figure,
    build_pd_scenario_projection_figure,
    build_pd_scenario_rank_figure,
    build_pd_sensitivity_combined_figure,
)
from .....components.filters import (
    build_chart_header,
    build_frozen_horizon_control,
    build_global_filters,
    build_range_controls,
    build_trend_horizon_control,
)
from .cards import (
    build_pd_chapter_heading,
    build_pd_ead_card,
    build_pd_overview_heatmap,
    build_pd_section_heading,
    build_pd_section_rag_card,
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
    get_pd_mev_scenario_quarter,
    get_pd_mev_visible_periods,
)
from .....data.analytics.rank_ordering import (
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
    precomputed_notching_components,
    precomputed_row,
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
    get_pd_threshold_metric_name,
    get_previous_pd_quarter,
    get_worst_pd_rag,
    pd_tone_class,
)

# ---------------------------------------------------------------------------
# Top-level component / store ids
# ---------------------------------------------------------------------------

from .....shared.theme import APP_THEME_ID, normalize_theme_value

CONTENT_ID = "pd-performance-content"
RANGE_STORE_ID = "pd-range-store"
TREND_HORIZON_STORE_ID = "pd-trend-horizon-store"
MEV_FILTER_STORE_ID = "pd-mev-filter-store"
APPLY_FILTERS_ID = "pd-apply-filters"
APPLIED_FILTERS_STORE_ID = "pd-applied-filters-store"
SCENARIO_RANKING_STORE_ID = "pd-scenario-ranking-store"
SCENARIO_RANKING_FILTER_ID = "pd-scenario-ranking-filter"

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


def _chart_surface(graph_id: str, figure, class_name: str) -> html.Div:
    """Wrap chapter-one charts in a contained surface so they align with cards."""
    return html.Div(
        className="pd-chart-card-surface",
        children=[
            dcc.Graph(
                id=graph_id,
                figure=figure,
                config=_GRAPH_CONFIG,
                className=f"{class_name} pd-chart-card-graph".strip(),
            )
        ],
    )


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
# PSI stability section helpers
# ---------------------------------------------------------------------------


def _safe_text(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and math.isnan(value):
        return fallback
    text = str(value).strip()
    return text or fallback


def _psi_rule_label(rule: str | None) -> str:
    rule_text = _safe_text(rule)
    if not rule_text:
        return "Not configured"
    return rule_text.replace("value", "PSI")


def _build_psi_threshold_chip(label: str, rule: str | None, tone: str, active_tone: str) -> html.Div:
    return html.Div(
        className=f"pd-psi-threshold-mini pd-psi-threshold-mini-{tone}{' is-active' if tone == active_tone else ''}",
        children=[
            html.Span(label),
            html.Strong(_psi_rule_label(rule)),
        ],
    )


def _build_psi_stability_card(
    threshold: dict,
    current_rag: str,
    monitoring_point: str,
) -> html.Article:
    active_tone = pd_tone_class(current_rag)
    return html.Article(
        className=f"pd-test-card pd-test-{active_tone} pd-psi-stability-card",
        children=[
            html.Div(
                className="pd-test-card-heading",
                children=[
                    html.Div([
                        html.Span("Stability test"),
                        html.Div([html.H4("PSI Stability RAG")], className="pd-card-title-row"),
                    ]),
                ],
            ),
            html.Div(current_rag, className="pd-test-value"),
            html.Div(f"Monitoring point: {monitoring_point}", className="pd-test-meta"),
            html.Div(
                className="pd-rag-card-method",
                children=[
                    html.Strong("Methodology: "),
                    "Population Stability Index on the IRB CRR key-driver distribution, comparing the current "
                    "performing-book population against the development reference.",
                ],
            ),
            html.Div(
                className="pd-psi-threshold-mini-grid",
                children=[
                    _build_psi_threshold_chip("Green", threshold.get("green_rule"), "green", active_tone),
                    _build_psi_threshold_chip("Amber", threshold.get("amber_rule"), "amber", active_tone),
                    _build_psi_threshold_chip("Red", threshold.get("red_rule"), "red", active_tone),
                ],
            ),
            html.Div(
                _safe_text(
                    threshold.get("notes"),
                    "Lower PSI values indicate a more stable population.",
                ),
                className="pd-test-footnote",
            ),
        ],
    )


def _build_psi_stability_summary(
    performance_trend: list[dict],
    thresholds: list[dict],
    monitoring_point: str,
) -> html.Div:
    metric_name = get_pd_threshold_metric_name("Population Stability Index")
    threshold = next((row for row in thresholds if row.get("metric") == metric_name), {})
    trend = [row for row in performance_trend if row.get("quarter") and row.get("quarter") <= monitoring_point]
    current_row = trend[-1] if trend else {}
    previous_row = trend[-2] if len(trend) > 1 else {}
    current_value = current_row.get("population_stability_index")
    previous_value = previous_row.get("population_stability_index")
    current_rag = calculate_pd_metric_rag(thresholds, "Population Stability Index", current_value)
    current_values = {"Population Stability Index": current_value}
    previous_values = {"Population Stability Index": previous_value}
    psi_context = {
        "monitoring_point": monitoring_point,
        "snapshot_quarter": current_row.get("quarter") or monitoring_point,
        "previous_quarter": previous_row.get("quarter") or "",
    }

    return html.Div(
        className="pd-test-grid pd-discrimination-test-grid pd-psi-test-grid",
        children=[
            _build_psi_stability_card(threshold, current_rag, monitoring_point),
            build_pd_test_card(
                "Population Stability Index", current_values, previous_values, thresholds, psi_context,
                options={
                    "card_title": "Population Stability Index",
                    "test_label": "PSI based on IRB CRR",
                    "format": "ratio",
                    "extra_meta_rows": [{"label": "Assessment", "value": "Current vs reference snapshot"}],
                    "tooltip": "Lower PSI indicates a more stable performing-book distribution.",
                },
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Scenario ranking and sensitivity analysis helpers
# ---------------------------------------------------------------------------


_PD_SCENARIO_ORDER = {"baseline": 0, "other": 1, "intsevere": 2, "baseline_2std_shock": 3}


def _format_pd_scenario_label(value: str | None) -> str:
    scenario = str(value or "").strip()
    return scenario or "Scenario"


def _resolve_pd_sensitivity_entity(ctx: PdFilterContext) -> tuple[str, str]:
    if ctx.segment and ctx.segment != "all":
        return "segment", ctx.segment
    models = sorted(model for model in ctx.models if model)
    if len(models) == 1:
        return "model", models[0]
    return "model", "All Models"


def _filter_pd_projection_rows(rows: list[dict], reporting_cycle: str, ctx: PdFilterContext) -> list[dict]:
    level, entity = _resolve_pd_sensitivity_entity(ctx)
    return [
        row for row in rows or []
        if row.get("reporting_cycle") == reporting_cycle
        and row.get("level") == level
        and row.get("model_or_segment") == entity
        and row.get("scenario_variant")
    ]


def _filter_pd_sensitivity_rows(rows: list[dict], reporting_cycle: str, ctx: PdFilterContext) -> list[dict]:
    return [
        row for row in _filter_pd_projection_rows(rows, reporting_cycle, ctx)
        if row.get("scenario_variant") in {"baseline", "baseline_2std_shock"}
    ]


def _available_pd_scenario_ranking_values(rows: list[dict]) -> list[str]:
    return sorted(
        {str(row.get("scenario_variant")) for row in rows if row.get("scenario_variant")},
        key=lambda scenario: (_PD_SCENARIO_ORDER.get(str(scenario).lower(), 99), str(scenario)),
    )


def _resolve_pd_scenario_ranking_selection(rows: list[dict], store: dict | None) -> list[str]:
    available = _available_pd_scenario_ranking_values(rows)
    if not available:
        return []
    selected = (store or {}).get("scenarios")
    if selected is None:
        return available
    return [scenario for scenario in selected if scenario in available]


def _build_pd_scenario_ranking_filter(rows: list[dict], selected_scenarios: list[str]) -> html.Div:
    available = _available_pd_scenario_ranking_values(rows)
    options = [
        {"label": _format_pd_scenario_label(scenario), "value": scenario}
        for scenario in available
    ]
    return html.Div(
        className="pd-scenario-ranking-filter-row",
        children=[
            html.Div(
                className="pd-scenario-ranking-filter-copy",
                children=[
                    html.Div("Scenario selection", className="pd-scenario-ranking-filter-title"),
                    html.P(
                        "Choose which scenario paths should be included in the ranking statistics and charts.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
            dcc.Checklist(
                id=SCENARIO_RANKING_FILTER_ID,
                options=options,
                value=selected_scenarios,
                className="pd-scenario-ranking-checklist",
                inputClassName="pd-scenario-ranking-check-input",
                labelClassName="pd-scenario-ranking-check-label",
            ),
        ],
    )


def _scenario_ranking_summary(rows: list[dict]) -> dict:
    scenarios = sorted(
        {str(row.get("scenario_variant")) for row in rows if row.get("scenario_variant")},
        key=lambda scenario: (_PD_SCENARIO_ORDER.get(str(scenario).lower(), 99), str(scenario)),
    )
    quarters = sorted({row.get("quarter") for row in rows if row.get("quarter") is not None})
    rows_by_quarter: dict[int, list[dict]] = {}
    rows_by_scenario: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("quarter") is not None:
            rows_by_quarter.setdefault(int(row["quarter"]), []).append(row)
        rows_by_scenario.setdefault(str(row.get("scenario_variant")), []).append(row)

    inversion_count = 0
    spreads = []
    for quarter in quarters:
        quarter_rows = rows_by_quarter.get(int(quarter), [])
        values_by_scenario = {
            str(row.get("scenario_variant")): row.get("projected_pd")
            for row in quarter_rows
            if row.get("projected_pd") is not None
        }
        ordered_values = [values_by_scenario.get(scenario) for scenario in scenarios]
        ordered_values = [value for value in ordered_values if value is not None]
        if len(ordered_values) >= 2 and any(ordered_values[index] > ordered_values[index + 1] for index in range(len(ordered_values) - 1)):
            inversion_count += 1
        if values_by_scenario:
            values = list(values_by_scenario.values())
            spreads.append(max(values) - min(values))

    average_by_scenario = {}
    for scenario, scenario_rows in rows_by_scenario.items():
        values = [row.get("projected_pd") for row in scenario_rows if row.get("projected_pd") is not None]
        if values:
            average_by_scenario[scenario] = sum(values) / len(values)
    highest_scenario = max(average_by_scenario, key=average_by_scenario.get) if average_by_scenario else None
    status = "Ranking maintained" if inversion_count == 0 and scenarios else "Rank inversion"

    return {
        "scenario_count": len(scenarios),
        "quarter_count": len(quarters),
        "inversion_count": inversion_count,
        "max_spread": max(spreads) if spreads else None,
        "highest_scenario": _format_pd_scenario_label(highest_scenario),
        "status": status,
        "tone": "green" if status == "Ranking maintained" else "red",
    }


def _format_sensitivity_pd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2%}"


def _build_pd_transition_delta_trend(data: dict, reporting_cycle: str, ctx: PdFilterContext) -> list[dict]:
    """Scenario-independent MM_Pm - MM_P0 delta per projection quarter.

    MM_P0 is a constant anchor and MM_Pm migrates over the horizon, so the
    margins are read once per projection quarter (they don't vary by scenario).
    """
    rows = _filter_pd_projection_rows(data.get("sensitivity_projections") or [], reporting_cycle, ctx)
    by_offset: dict[int, dict] = {}
    for row in rows:
        offset = row.get("quarter")
        mm_p0 = row.get("mm_p0")
        mm_pm = row.get("mm_pm")
        if offset is None or mm_p0 is None or mm_pm is None or int(offset) in by_offset:
            continue
        by_offset[int(offset)] = {
            "offset": int(offset),
            "label": f"Q{int(offset)}",
            "period": iso_date_to_pd_quarter(row.get("projection_quarter")),
            "mm_p0": mm_p0,
            "mm_pm": mm_pm,
            "delta": mm_pm - mm_p0,
        }
    return [by_offset[key] for key in sorted(by_offset)]


def _rag_tone(rag: str) -> str:
    return {"Green": "green", "Amber": "amber", "Red": "red"}.get(rag, "neutral")


def _build_pd_transition_matrix_section(
    data: dict,
    ctx: PdFilterContext,
    reporting_cycle: str,
    theme: str,
    range_store: dict | None = None,
) -> html.Section:
    range_store = range_store or {}
    trend = _build_pd_transition_delta_trend(data, reporting_cycle, ctx)
    heading = build_pd_section_heading(
        "2.2 Transition Matrix", "Transition Matrix",
        "Migration of the through-the-horizon PD (MM_Pm) away from its anchor (MM_P0). The delta widens as the "
        "transition structure drifts from the reference, independent of macro scenario.",
        "N/A", options={"show_rag": False},
    )

    if not trend:
        return html.Section(
            id="pd-transition-matrix-distance",
            className="pd-content-section pd-placeholder-section",
            children=[
                heading,
                _build_placeholder_card(
                    "Transition Matrix",
                    "No MM_P0 / MM_Pm margin data is available for the selected reporting cycle and population.",
                    ["Transition view", "Distance metric", "Threshold guidance"],
                ),
            ],
        )

    from .....data.analytics.calculations import calculate_pd_metric_rag, get_pd_thresholds

    thresholds = get_pd_thresholds(data.get("monitoring_thresholds") or {})
    _rank = {"Green": 0, "Amber": 1, "Red": 2, "N/A": -1}
    peak = max(trend, key=lambda row: row["delta"])
    # Overall status = the worst RAG seen anywhere across the horizon.
    overall_rag = max(
        (calculate_pd_metric_rag(thresholds, "Transition Matrix", row["delta"]) for row in trend),
        key=lambda rag: _rank.get(rag, -1),
    )
    breaches = sum(
        1 for row in trend
        if calculate_pd_metric_rag(thresholds, "Transition Matrix", row["delta"]) in ("Amber", "Red")
    )

    return html.Section(
        id="pd-transition-matrix-distance",
        className="pd-content-section pd-live-section",
        children=[
            heading,
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"},
                children=[
                    _build_rag_status_card(
                        "Migration test",
                        "Transition Matrix RAG",
                        overall_rag,
                        ctx.monitoring_point,
                        "Worst-case migration gap (MM_Pm − MM_P0) across the projection horizon, scored against the "
                        "Transition Matrix distance threshold.",
                        [("Green", "Δ < 15%", "green"), ("Amber", "15–30%", "amber"), ("Red", "Δ > 30%", "red")],
                        footnote="Lower delta means the migrated PD stays closer to the reference anchor.",
                    ),
                    html.Article(
                        className=f"pd-test-card pd-test-{'red' if overall_rag == 'Red' else ('amber' if breaches else 'green')}",
                        children=[
                            html.Div(
                                className="pd-test-card-heading",
                                children=[html.Div([html.Div([html.H4("Threshold Breaches")], className="pd-card-title-row")])],
                            ),
                            html.Div(f"{breaches} / {len(trend)}", className="pd-test-value"),
                            html.Div("quarters breach the Transition Matrix threshold", className="pd-test-meta"),
                            html.Div(
                                className="pd-test-card-heading",
                                style={"marginTop": "14px"},
                                children=[html.Div([html.Div([html.H4("Peak migration delta")], className="pd-card-title-row")])],
                            ),
                            html.Div(f"{peak['delta']:.2%}", className="pd-test-value"),
                            html.Div(f"Largest gap, reached at {peak['period']}.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="pd-transition-combined-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Transition Margins & Delta",
                        "MM_P0 anchor vs MM_Pm migrated PD (left) and their RAG-rated delta (right) "
                        "across the projection horizon.",
                    ),
                    dcc.Graph(
                        id="pd-transition-combined-chart",
                        figure=build_pd_transition_combined_figure(
                            trend,
                            range_value=None,
                            monitoring_thresholds=data.get("monitoring_thresholds"),
                            theme=theme,
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart",
                    ),
                ],
            ),
        ],
    )


def _build_pd_scenario_ranking_section(
    data: dict,
    ctx: PdFilterContext,
    reporting_cycle: str,
    theme: str,
    scenario_ranking_store: dict | None = None,
) -> html.Section:
    available_rows = _filter_pd_projection_rows(data.get("sensitivity_projections") or [], reporting_cycle, ctx)
    selected_scenarios = _resolve_pd_scenario_ranking_selection(available_rows, scenario_ranking_store)
    rows = [
        row for row in available_rows
        if row.get("scenario_variant") in selected_scenarios
    ]
    level, entity = _resolve_pd_sensitivity_entity(ctx)
    summary = _scenario_ranking_summary(rows)
    filter_control = _build_pd_scenario_ranking_filter(available_rows, selected_scenarios)

    if rows:
        body = [
            filter_control,
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"},
                children=[
                    _build_rag_status_card(
                        "Ranking test",
                        "Scenario Ranking RAG",
                        summary["status"],
                        ctx.monitoring_point,
                        "Checks whether projected PD stays ordered by scenario severity in every projection quarter; "
                        "any quarter where a milder scenario outranks a more severe one is an inversion.",
                        [("Green", "0 inversions", "green"), ("Red", "≥ 1 inversion", "red")],
                        footnote=f"{summary['inversion_count']} inversion(s) across {summary['quarter_count']} quarters.",
                        tone=summary["tone"],
                    ),
                    html.Article(
                        className="pd-test-card pd-test-neutral",
                        children=[
                            html.Div(
                                className="pd-test-card-heading",
                                children=[html.Div([html.Div([html.H4("Maximum PD spread")], className="pd-card-title-row")])],
                            ),
                            html.Div(_format_sensitivity_pd(summary["max_spread"]), className="pd-test-value"),
                            html.Div("Largest high-minus-low scenario gap across projection quarters.", className="pd-test-meta"),
                            html.Div(
                                className="pd-test-card-heading",
                                style={"marginTop": "14px"},
                                children=[html.Div([html.Div([html.H4("Highest average PD")], className="pd-card-title-row")])],
                            ),
                            html.Div(summary["highest_scenario"], className="pd-test-value"),
                            html.Div(f"Across {summary['scenario_count']} selected scenario paths.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="pd-sensitivity-chart-grid",
                children=[
                    html.Div(
                        className="section-card pd-default-rate-trend-section pd-sensitivity-chart-card",
                        children=[
                            build_chart_header(
                                "Projected PD by Scenario",
                                f"{entity} ({level}) projected PD paths for selected scenarios.",
                            ),
                            dcc.Graph(
                                id="pd-scenario-projection-chart",
                                figure=build_pd_scenario_projection_figure(rows, theme=theme),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium",
                            ),
                        ],
                    ),
                    html.Div(
                        className="section-card pd-default-rate-trend-section pd-sensitivity-chart-card",
                        children=[
                            build_chart_header(
                                "Scenario Rank Matrix",
                                "Rank 1 identifies the scenario with the highest projected PD in each projection quarter.",
                            ),
                            dcc.Graph(
                                id="pd-scenario-rank-chart",
                                figure=build_pd_scenario_rank_figure(rows, theme=theme),
                                config=_GRAPH_CONFIG,
                                className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium",
                            ),
                        ],
                    ),
                ],
            ),
        ]
    else:
        body = [
            filter_control,
            html.Div(
                className="section-card pd-mev-empty-state",
                children=[
                    html.Div("No scenario projection data matches the current scenario selection", className="pd-mev-chart-title"),
                    html.P(
                        "Select at least one available scenario, or choose a reporting cycle, segment, or specific model that exists in the PD_Sensitivity_Projections workbook sheet.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
        ]

    return html.Section(
        id="pd-scenario-ranking",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Scenario Ranking",
                "Scenario Ranking",
                "Compares projected PD paths across selected scenarios and checks whether higher-stress scenarios "
                "consistently rank above lower-stress paths. Any rank inversion suggests the scenario response may "
                "need business review. Use the scenario selector to include or exclude available paths.",
                "N/A",
                options={"show_rag": False},
            ),
            *body,
        ],
    )


def _get_pd_sensitivity_threshold(monitoring_thresholds: dict) -> dict:
    rows = (monitoring_thresholds or {}).get("scenario_test_thresholds") or []
    threshold = next(
        (
            row for row in rows
            if str(row.get("test", "")).strip().lower() == "sensitivity analysis"
            and str(row.get("model_type", "")).strip().upper() == "PD"
        ),
        {},
    )
    value = threshold.get("threshold")
    try:
        threshold_value = float(value)
    except (TypeError, ValueError):
        threshold_value = None
    return {**threshold, "threshold": threshold_value}


def _sensitivity_impact_summary(rows: list[dict], threshold: float | None) -> dict:
    baseline_by_offset = {
        row.get("quarter"): row.get("projected_pd")
        for row in rows
        if row.get("scenario_variant") == "baseline"
    }
    impacts = []
    for row in rows:
        if row.get("scenario_variant") != "baseline_2std_shock":
            continue
        baseline = baseline_by_offset.get(row.get("quarter"))
        shocked = row.get("projected_pd")
        if baseline and shocked is not None and baseline > 0:
            impacts.append(abs(shocked - baseline) / baseline)

    if not impacts:
        return {
            "average_impact": None,
            "max_impact": None,
            "within_count": 0,
            "total_count": 0,
            "status": "N/A",
            "tone": "neutral",
        }

    within_count = sum(1 for impact in impacts if threshold is not None and impact <= threshold)
    if threshold is None:
        status = "Threshold unavailable"
        tone = "neutral"
    elif within_count == len(impacts):
        status = "Within threshold"
        tone = "green"
    else:
        status = "Threshold breach"
        tone = "red"
    return {
        "average_impact": sum(impacts) / len(impacts),
        "max_impact": max(impacts),
        "within_count": within_count,
        "total_count": len(impacts),
        "status": status,
        "tone": tone,
    }


def _format_sensitivity_percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1%}"


def _build_rag_status_card(
    kicker: str,
    title: str,
    rag: str,
    monitoring_point: str,
    methodology,
    threshold_chips: list[tuple[str, str, str]],
    footnote: str | None = None,
    tone: str | None = None,
) -> html.Article:
    """RAG status card with monitoring point, methodology, and threshold chips.

    ``threshold_chips`` is a list of ``(label, rule_text, tone)`` tuples
    (tone in {"green", "amber", "red"}). ``tone`` overrides the card tone when
    the ``rag`` value is not a standard Green/Amber/Red label.
    """
    active_tone = tone or pd_tone_class(rag)
    children = [
        html.Div(
            className="pd-test-card-heading",
            children=[html.Div([
                html.Span(kicker),
                html.Div([html.H4(title)], className="pd-card-title-row"),
            ])],
        ),
        html.Div(rag, className="pd-test-value"),
        html.Div(f"Monitoring point: {monitoring_point}", className="pd-test-meta"),
        html.Div(
            className="pd-rag-card-method",
            children=[html.Strong("Methodology: "), *(methodology if isinstance(methodology, list) else [methodology])],
        ),
        html.Div(
            className="pd-psi-threshold-mini-grid",
            children=[
                _build_psi_threshold_chip(label, rule, tone, active_tone)
                for label, rule, tone in threshold_chips
            ],
        ),
    ]
    if footnote:
        children.append(html.Div(footnote, className="pd-test-footnote"))
    return html.Article(className=f"pd-test-card pd-test-{active_tone}", children=children)


def _build_pd_sensitivity_section(data: dict, ctx: PdFilterContext, reporting_cycle: str, theme: str, range_store: dict | None = None) -> html.Section:
    range_store = range_store or {}
    rows = _filter_pd_sensitivity_rows(data.get("sensitivity_projections") or [], reporting_cycle, ctx)
    level, entity = _resolve_pd_sensitivity_entity(ctx)
    threshold_row = _get_pd_sensitivity_threshold(data.get("monitoring_thresholds") or {})
    threshold_value = threshold_row.get("threshold")
    impact_summary = _sensitivity_impact_summary(rows, threshold_value)
    threshold_label = _format_sensitivity_percent(threshold_value)

    if rows:
        breaches = impact_summary["total_count"] - impact_summary["within_count"]
        body = [
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"},
                children=[
                    _build_rag_status_card(
                        "Sensitivity test",
                        "Scenario Test RAG",
                        impact_summary["status"],
                        ctx.monitoring_point,
                        "Per quarter, abs(shocked − baseline) / baseline measures how reactive projected PD is to a "
                        "2SD adverse MEV shock; a breach in any quarter turns the test Red.",
                        [("Green", f"≤ {threshold_label}", "green"), ("Red", f"> {threshold_label}", "red")],
                        footnote="Lower relative impact means projected PD is less reactive to the macro shock.",
                        tone=impact_summary["tone"],
                    ),
                    html.Article(
                        className=f"pd-test-card pd-test-{'red' if breaches else 'green'}",
                        children=[
                            html.Div(
                                className="pd-test-card-heading",
                                children=[html.Div([html.Div([html.H4("Threshold Breaches")], className="pd-card-title-row")])],
                            ),
                            html.Div(f"{breaches} / {impact_summary['total_count']}", className="pd-test-value"),
                            html.Div(f"quarters above the {threshold_label} scenario-test threshold", className="pd-test-meta"),
                            html.Div(
                                className="pd-test-card-heading",
                                style={"marginTop": "14px"},
                                children=[html.Div([html.Div([html.H4("Peak Relative Impact")], className="pd-card-title-row")])],
                            ),
                            html.Div(_format_sensitivity_percent(impact_summary["max_impact"]), className="pd-test-value"),
                            html.Div("Largest abs(shocked − baseline) / baseline across the horizon.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id="pd-sensitivity-combined-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Projected PD Sensitivity & Relative Shock Impact",
                        f"{entity} ({level}): baseline vs 2SD-shock projected PD (left) and the relative shock "
                        "impact by quarter (right), RAG-rated against the scenario-test threshold.",
                    ),
                    dcc.Graph(
                        id="pd-sensitivity-combined-chart",
                        figure=build_pd_sensitivity_combined_figure(
                            rows, threshold_value,
                            range_value=None,
                            theme=theme,
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart",
                    ),
                ],
            ),
        ]
    else:
        body = [
            html.Div(
                className="section-card pd-mev-empty-state",
                children=[
                    html.Div("No sensitivity projection data matches the current filters", className="pd-mev-chart-title"),
                    html.P(
                        "Choose a reporting cycle, segment, or specific model that exists in the PD_Sensitivity_Projections workbook sheet.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
        ]

    return html.Section(
        id="pd-sensitivity-analysis",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.5 Sensitivity Analysis",
                "Sensitivity Analysis",
                "Compares baseline projected PD values against a simultaneous 2 standard deviation shock applied to transformed MEVs.",
                "N/A",
                options={"show_rag": False},
            ),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# 2.1 Post Subjective Review Analysis Overview (review scorecard)
# ---------------------------------------------------------------------------

_RAG_RANK = {"N/A": -1, "Green": 0, "Amber": 1, "Red": 2}
_RAG_HEX = {"green": "#16a34a", "amber": "#d97706", "red": "#dc2626", "neutral": "#94a3b8"}


def _worst_rag(rags: list[str]) -> str:
    rags = [r for r in rags if r]
    return max(rags, key=lambda r: _RAG_RANK.get(r, -1)) if rags else "N/A"


def _pd_post_review_summaries(
    data: dict,
    ctx: PdFilterContext,
    reporting_cycle: str,
    scenario: str,
    observations,
    rating_observations,
    cq: str,
    crr_scale,
) -> list[dict]:
    """Headline status + key metric + takeaway for each Chapter 2 test."""
    from .....data.analytics.calculations import (
        build_pd_performance_trend_for_horizon,
        calculate_pd_metric_rag,
        get_pd_thresholds,
    )

    monitoring_thresholds = data.get("monitoring_thresholds") or {}
    thresholds = get_pd_thresholds(monitoring_thresholds)
    projections = data.get("sensitivity_projections") or []
    summaries: list[dict] = []

    # 2.2 Transition Matrix -------------------------------------------------
    trend = _build_pd_transition_delta_trend(data, reporting_cycle, ctx)
    if trend:
        rags = [calculate_pd_metric_rag(thresholds, "Transition Matrix", row["delta"]) for row in trend]
        peak = max(trend, key=lambda row: row["delta"])
        breaches = sum(1 for r in rags if r in ("Amber", "Red"))
        summaries.append({
            "name": "Transition Matrix", "anchor": "pd-transition-matrix-distance", "rag": _worst_rag(rags),
            "metric": f"{peak['delta']:.1%}", "metric_label": "Peak migration gap",
            "takeaway": f"MM_Pm drifts {peak['delta']:.1%} from anchor by {peak['period']} · "
                        f"{breaches}/{len(trend)} quarters breach threshold.",
        })
    else:
        summaries.append({
            "name": "Transition Matrix", "anchor": "pd-transition-matrix-distance", "rag": "N/A",
            "metric": "—", "metric_label": "Peak migration gap",
            "takeaway": "No MM_P0 / MM_Pm margin data for the current scope.",
        })

    # 2.3 PSI ---------------------------------------------------------------
    psi_trend = build_pd_performance_trend_for_horizon(observations, rating_observations, cq, "1y", ctx, crr_scale)
    psi_rows = [r for r in psi_trend if r.get("quarter") and r["quarter"] <= cq]
    latest_psi = psi_rows[-1].get("population_stability_index") if psi_rows else None
    psi_rag = calculate_pd_metric_rag(thresholds, "Population Stability Index", latest_psi)
    summaries.append({
        "name": "PSI", "anchor": "pd-population-stability-index", "rag": psi_rag,
        "metric": f"{latest_psi:.3f}" if latest_psi is not None else "—", "metric_label": f"Latest PSI ({cq})",
        "takeaway": "Population stability vs reference — lower is more stable (green ≤ 0.10, red > 0.25).",
    })

    # 2.4 Scenario Ranking --------------------------------------------------
    sr_rows = _filter_pd_projection_rows(projections, reporting_cycle, ctx)
    if sr_rows:
        sr = _scenario_ranking_summary(sr_rows)
        sr_rag = "Green" if sr["status"] == "Ranking maintained" else "Red"
        summaries.append({
            "name": "Scenario Ranking", "anchor": "pd-scenario-ranking", "rag": sr_rag,
            "metric": sr["status"], "metric_label": f"{sr['scenario_count']} scenario paths",
            "takeaway": f"{sr['inversion_count']} rank inversion(s) over {sr['quarter_count']} quarters · "
                        f"max spread {_format_sensitivity_pd(sr['max_spread'])}.",
        })
    else:
        summaries.append({
            "name": "Scenario Ranking", "anchor": "pd-scenario-ranking", "rag": "N/A",
            "metric": "—", "metric_label": "scenario paths",
            "takeaway": "No scenario projection data for the current scope.",
        })

    # 2.5 Sensitivity Analysis ---------------------------------------------
    threshold_value = _get_pd_sensitivity_threshold(monitoring_thresholds).get("threshold")
    sens_rows = _filter_pd_sensitivity_rows(projections, reporting_cycle, ctx)
    sens = _sensitivity_impact_summary(sens_rows, threshold_value)
    sens_breaches = sens["total_count"] - sens["within_count"]
    sens_rag = {"green": "Green", "red": "Red"}.get(sens["tone"], "N/A")
    summaries.append({
        "name": "Sensitivity Analysis", "anchor": "pd-sensitivity-analysis", "rag": sens_rag,
        "metric": _format_sensitivity_percent(sens["max_impact"]), "metric_label": "Peak shock impact",
        "takeaway": f"{sens_breaches}/{sens['total_count']} quarters above the "
                    f"{_format_sensitivity_percent(threshold_value)} threshold." if sens["total_count"]
                    else "No sensitivity projection data for the current scope.",
    })

    # 2.6 MEV Range ---------------------------------------------------------
    catalog = data.get("mev_catalog") or {}
    counts = {"Green": 0, "Amber": 0, "Red": 0, "N/A": 0}
    total = 0
    for model_name in get_pd_mev_selected_models(catalog, ctx):
        model_data = catalog.get(model_name, {})
        for _, mev_data in (model_data.get("mevs") or {}).items():
            sq = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
            rag = calculate_pd_mev_worst_rag_after_quarter(mev_data, sq, reporting_cycle, scenario)
            counts[rag] = counts.get(rag, 0) + 1
            total += 1
    breached = counts["Red"] + counts["Amber"]
    mev_rag = "Red" if counts["Red"] else ("Amber" if counts["Amber"] else ("Green" if total else "N/A"))
    summaries.append({
        "name": "MEV Range", "anchor": "pd-mev-range", "rag": mev_rag,
        "metric": f"{breached}/{total}" if total else "—", "metric_label": "MEVs outside dev range",
        "takeaway": (f"{counts['Red']} red · {counts['Amber']} amber across {total} MEVs at the {scenario} scenario."
                     if total else "No MEVs in scope for the current scenario."),
    })

    return summaries


def _build_pd_review_scorecard_card(summary: dict) -> html.Article:
    tone = _rag_tone(summary["rag"])
    return html.Article(
        className=f"pd-test-card pd-test-{tone} pd-review-card",
        children=[
            html.Div(
                className="pd-card-title-row",
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "8px"},
                children=[
                    html.H4(summary["name"]),
                    html.Span(
                        summary["rag"],
                        style={
                            "flex": "0 0 auto", "fontSize": "11px", "fontWeight": "800", "letterSpacing": "0.3px",
                            "color": _RAG_HEX.get(tone, "#94a3b8"),
                        },
                    ),
                ],
            ),
            html.Div(summary["metric"], className="pd-test-value", style={"marginTop": "10px"}),
            html.Div(
                summary["metric_label"], className="pd-test-meta",
                style={"fontWeight": "700", "textTransform": "uppercase", "fontSize": "9.5px",
                       "letterSpacing": "0.35px", "color": "#64748b", "marginTop": "2px"},
            ),
            html.Div(summary["takeaway"], className="pd-test-meta", style={"marginTop": "8px"}),
        ],
    )


def _build_pd_post_review_overview(
    data: dict,
    ctx: PdFilterContext,
    reporting_cycle: str,
    scenario: str,
    observations,
    rating_observations,
    cq: str,
    crr_scale,
) -> html.Section:
    summaries = _pd_post_review_summaries(
        data, ctx, reporting_cycle, scenario, observations, rating_observations, cq, crr_scale,
    )
    attention = [s for s in summaries if s["rag"] in ("Amber", "Red")]
    red = sum(1 for s in summaries if s["rag"] == "Red")
    amber = sum(1 for s in summaries if s["rag"] == "Amber")
    green = sum(1 for s in summaries if s["rag"] == "Green")
    posture_tone = "red" if red else ("amber" if amber else "green")

    def _legend(label: str, count: int, tone: str) -> html.Div:
        return html.Div(
            className="pd-review-legend-chip",
            style={"display": "inline-flex", "alignItems": "center", "gap": "7px", "padding": "6px 11px",
                   "border": "1px solid #dbe4f0", "borderRadius": "999px", "background": "rgba(248,250,252,.9)"},
            children=[
                html.Span(style={"width": "10px", "height": "10px", "borderRadius": "999px",
                                 "background": _RAG_HEX[tone], "boxShadow": "0 0 0 2px rgba(255,255,255,.9) inset"}),
                html.Strong(str(count), style={"fontSize": "13px", "color": "#0f172a"}),
                html.Span(label, style={"fontSize": "11px", "color": "#64748b", "fontWeight": "700"}),
            ],
        )

    return html.Section(
        id="pd-post-subjective-overview",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 Overview",
                "PD Post Subjective Review Analysis Overview",
                "At-a-glance health of every post subjective review test for the current scope. Each card shows the "
                "worst-case RAG across the projection horizon, a headline metric, and a one-line takeaway.",
                "N/A", options={"show_rag": False},
            ),
            html.Div(
                className="overview-command-hero",
                style={"marginBottom": "16px", "padding": "18px 20px"},
                children=[
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "alignItems": "center",
                               "justifyContent": "space-between", "gap": "14px"},
                        children=[
                            html.Div(children=[
                                html.Div("Review posture", className="overview-command-hero-kicker"),
                                html.H4(
                                    f"{len(attention)} of {len(summaries)} areas need attention",
                                    style={"margin": "0", "color": _RAG_HEX[posture_tone]},
                                ),
                            ]),
                            html.Div(
                                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                                children=[_legend("Red", red, "red"), _legend("Amber", amber, "amber"), _legend("Green", green, "green")],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(5, minmax(0, 1fr))"},
                children=[_build_pd_review_scorecard_card(s) for s in summaries],
            ),
        ],
    )


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
# 2.5 MEV Range helpers
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


def _build_mev_marker_items(
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
        _mev_marker_legend_item("Scenario", scenario, "series", line_color=scenario_color, line_dash="solid")
    )
    development_date = (mev_data.get("dev_range") or {}).get("development_date")
    if development_date:
        dev_label = str(development_date).replace("-Q", "Q")
        items.append(_mev_marker_legend_item("Development Date", dev_label, "development"))
    scenario_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
    if scenario_quarter:
        items.append(
            _mev_marker_legend_item("Scenario Date", str(scenario_quarter).replace("-Q", "Q"), "current")
        )
    return items


def _build_mev_monitoring_summary(
    thresholds: dict | None,
    model_data: dict,
    mev_data: dict,
    monitoring_point: str | None,
    theme_value: str | None = None,
    scenario: str = "intsevere",
    reporting_cycle: str | None = None,
):
    threshold_items = _build_mev_threshold_chips(thresholds)
    marker_items = _build_mev_marker_items(
        model_data,
        mev_data,
        monitoring_point,
        theme_value,
        scenario=scenario,
        reporting_cycle=reporting_cycle,
    )

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



def _format_mev_quarter(value: str | None) -> str:
    """Format a development/quarter value as ``YYYYQn``."""
    if not value:
        return "—"
    return str(value).replace("-Q", "Q")


def _build_mev_rag_summary_panel(
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
                mev_data,
                severe_quarter,
                reporting_cycle=reporting_cycle,
                scenario=scenario,
            )
            contrib = contributions.get(mev_name)
            mev_rags.append({"name": mev_name, "rag": rag, "contribution": contrib})
        mev_rags.sort(key=lambda entry: (-(entry.get("contribution") or 0), entry["name"]))
        worst = min(mev_rags, key=lambda e: _mev_rag_sort_weight(e["rag"]))["rag"] if mev_rags else "N/A"
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
                html.Div("No PD models in scope", className="pd-mev-chart-title"),
                html.P("Adjust the dashboard filters above to bring models into scope.", className="pd-section-subtitle"),
            ],
        )

    model_rows = []
    for summary in summaries:
        worst = summary["worst_rag"]
        worst_tone = worst.lower() if worst in ("Green", "Amber", "Red") else "na"
        dev_label = " / ".join(_format_mev_quarter(d) for d in summary["development_dates"]) if summary["development_dates"] else "—"
        severe_label = _format_mev_quarter(summary["severe_quarter"]) if summary["severe_quarter"] else (monitoring_point or "—")

        strip_segments = []
        for entry in summary["mev_rags"]:
            contrib = entry.get("contribution")
            if contrib is None or contrib <= 0:
                continue
            tone = entry["rag"].lower() if entry["rag"] in ("Green", "Amber", "Red") else "na"
            pct_val = contrib * 100
            pct_label = f"{pct_val:.0f}%"
            seg_children = [
                html.Span(entry["name"], className="pd-mev-strip-name"),
                html.Span(pct_label, className="pd-mev-strip-pct"),
            ]
            strip_segments.append(
                html.Div(
                    className=f"pd-mev-strip-seg pd-mev-strip-seg-{tone}",
                    style={"flex": str(contrib)},
                    title=f"{entry['name']}: {pct_label} — RAG {entry['rag']}",
                    children=seg_children,
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
                        children=[
                            html.Div(strip_segments, className="pd-mev-strip"),
                        ],
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




# ---------------------------------------------------------------------------
# 2.6 MEV Range (buildPdMevRangeSection)
# ---------------------------------------------------------------------------


def _build_mev_range_section(data: dict, ctx: PdFilterContext, range_store: dict, mev_filter_store: dict, theme_value: str | None = None, reporting_cycle: str = "CCAR 2026", scenario: str = "intsevere") -> html.Section:
    catalog = data["mev_catalog"]
    mev_mnemonic_map = data.get("mev_mnemonic_map") or {}
    mev_description_map = data.get("mev_description_map") or {}
    selected_models = get_pd_mev_selected_models(catalog, ctx)

    chart_model_names = resolve_pd_mev_chart_model_names(selected_models, mev_filter_store.get("model"))
    available_mev_names = get_pd_mev_available_names_for_models(catalog, chart_model_names)
    chart_mev_names = resolve_pd_mev_chart_names(available_mev_names, mev_filter_store.get("names"))
    mev_periods = get_pd_mev_visible_periods(catalog, chart_model_names, chart_mev_names)


    model_panels = []
    for model_index, model_name in enumerate(chart_model_names):
        model_data = catalog.get(model_name, {})
        mev_entries = sorted(
            ((name, mdata) for name, mdata in (model_data.get("mevs") or {}).items() if name in chart_mev_names),
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
        for mev_index, (mev_name, mev_data) in enumerate(mev_entries):
            mev_mnemonic = mev_mnemonic_map.get(mev_name, mev_name)
            mev_description = mev_description_map.get(mev_name, "")
            thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
            chart_id = get_pd_mev_chart_id(model_name, mev_name)
            theme = normalize_theme_value(theme_value)
            trace_color = "#fb7185" if theme == "dark" else "#dc2626"
            fig = build_pd_mev_range_figure(
                model_data,
                mev_name,
                mev_data,
                trace_color,
                range_store.get("mev"),
                theme=theme,
                reporting_cycle=reporting_cycle,
                scenario=scenario,
            )
            monitoring_summary = _build_mev_monitoring_summary(
                thresholds,
                model_data,
                mev_data,
                ctx.monitoring_point,
                theme_value,
                scenario=scenario,
                reporting_cycle=reporting_cycle,
            )
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
                                className="pd-mev-model-meta",
                                children=[
                                    html.Div([
                                        html.Span("MEVs", className="pd-mev-model-meta-label"),
                                        html.Span(f"{len(mev_entries)}", className="pd-mev-model-meta-value"),
                                    ], className="pd-mev-model-meta-item"),
                                    html.Div([
                                        html.Span(f"Scenario: {scenario}", className="pd-mev-model-meta-label"),
                                        html.Span(
                                            _format_mev_quarter(scenario_quarter),
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
                "Checks whether the macro-economic variables (MEVs) driving PD models under stress remain within their trained operating range.",
                "N/A",
                options={
                    "show_rag": False,
                    "tooltip": (
                        "MEV Range charts, scenario date, and post-scenario RAG are based on the selected "
                        "Reporting Cycle value. The Monitoring Point controls the PD performance snapshot, "
                        "but it does not move the MEV scenario Q0 date."
                    ),
                },
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
                    "which may affect model reliability. For detailed MEV time series and scenario comparisons, see the ",
                    dcc.Link("SAAS Workspace", href="/saas", className="pd-inline-link"),
                    " tab.",
                ],
            ),
            _build_mev_rag_summary_panel(
                selected_models,
                catalog,
                ctx.monitoring_point,
                reporting_cycle=reporting_cycle,
                scenario=scenario,
            ),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# Main render function (renderPdModels)
# ---------------------------------------------------------------------------


def render_pd_performance_content(
    data: dict,
    ctx: PdFilterContext,
    range_store: dict,
    trend_horizon_store: dict,
    mev_filter_store: dict,
    scenario_ranking_store: dict | None = None,
    theme_value: str | None = None,
    reporting_cycle: str = "CCAR 2026",
    scenario: str = "intsevere",
) -> list:
    theme = normalize_theme_value(theme_value)
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
    has_current_data = (
        precomputed_row(ctx, context["snapshot_quarter"], "1y") is not None
        or current_rows
    )
    if not has_current_data:
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

    balance_sheet_notching = precomputed_notching_components(ctx, balance_sheet_context["snapshot_quarter"], "nco_1y", crr_scale) or calculate_pd_notching_components(
        filter_pd_performance_observations_for_horizon(observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx), crr_scale,
    )
    previous_balance_sheet_notching = precomputed_notching_components(ctx, balance_sheet_context["previous_quarter"], "nco_1y", crr_scale) or calculate_pd_notching_components(
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
    has_balance_sheet_data = (
        precomputed_row(ctx, balance_sheet_context["snapshot_quarter"], "nco_1y") is not None
        or filter_pd_performance_observations_for_horizon(observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx)
    )
    if not has_balance_sheet_data:
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
        horizon_notching = precomputed_notching_components(ctx, horizon_context["snapshot_quarter"], horizon_key, crr_scale) or calculate_pd_notching_components(
            filter_pd_performance_observations_for_horizon(observations, horizon_context["snapshot_quarter"], horizon_key, ctx), crr_scale,
        )
        previous_horizon_notching = precomputed_notching_components(ctx, horizon_context["previous_quarter"], horizon_key, crr_scale) or calculate_pd_notching_components(
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
                    html.H3("PD RAG Assignment Overview"),
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
                            _chart_surface(
                                "pd-calibration-rag-trend-chart",
                                build_pd_calibration_rag_trend_figure(calibration_rag_trend, cq, range_store.get("calibration_rag")),
                                "pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
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
                            _chart_surface(
                                "pd-confidence-interval-trend-chart",
                                build_pd_confidence_interval_trend_figure(
                                    calibration_performance_trend, monitoring_thresholds, calibration_trend_context["snapshot_quarter"], range_store.get("calibration_ci"), theme=theme,
                                ),
                                "pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
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
                    _chart_surface(
                        "pd-notching-trend-chart",
                        build_pd_notching_trend_figure(calibration_performance_trend, monitoring_thresholds, range_store.get("calibration_notching"), theme=theme),
                        "pd-default-rate-trend-chart pd-notching-trend-chart",
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
                    _chart_surface(
                        "pd-default-rate-trend-chart",
                        build_pd_default_rate_trend_figure(calibration_performance_trend, monitoring_thresholds, range_store.get("calibration_default_rate"), theme=theme),
                        "pd-default-rate-trend-chart pd-calibration-trend-chart",
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
        discrimination_performance_trend, monitoring_thresholds, discrimination_trend_context["snapshot_quarter"], range_store.get("discrimination_trend"), theme=theme,
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
                    _chart_surface(
                        "pd-discrimination-rag-trend-chart",
                        build_pd_discrimination_rag_trend_figure(discrimination_rag_trend, cq, range_store.get("discrimination_rag")),
                        "pd-default-rate-trend-chart pd-default-rate-trend-chart-compact",
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
                    _chart_surface(
                        "pd-go-live-accuracy-trend-chart",
                        build_pd_go_live_accuracy_trend_figure(go_live_performance_trend, monitoring_thresholds, go_live_start, range_store.get("discrimination_accuracy"), theme=theme),
                        "pd-default-rate-trend-chart pd-go-live-accuracy-trend-chart",
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
                            _chart_surface(
                                "pd-discrimination-trend-gini-coefficient",
                                discrimination_trend_figures["gini_coefficient"],
                                "pd-discrimination-trend-chart",
                            ),
                            _chart_surface(
                                "pd-discrimination-trend-ks-statistic",
                                discrimination_trend_figures["ks_statistic"],
                                "pd-discrimination-trend-chart",
                            ),
                            _chart_surface(
                                "pd-discrimination-trend-kendall-tau",
                                discrimination_trend_figures["kendall_tau"],
                                "pd-discrimination-trend-chart",
                            ),
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
                "Assess balance sheet PD calibration using the same framework as ECL PIT calibration, "
                "evaluating the 1-year population with CPD NCO as the predicted PD source.",
                "N/A",
                options={"show_rag": False},
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
                            _chart_surface(
                                "pd-balance-sheet-calibration-rag-trend-chart",
                                build_pd_balance_sheet_calibration_rag_trend_figure(balance_sheet_rag_trend, balance_sheet_context["snapshot_quarter"], range_store.get("balance_sheet_calibration_rag")),
                                "pd-default-rate-trend-chart pd-default-rate-trend-chart-compact pd-default-rate-trend-chart-axis-room-compact",
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
                            _chart_surface(
                                "pd-balance-sheet-confidence-interval-trend-chart",
                                build_pd_confidence_interval_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, balance_sheet_context["snapshot_quarter"], range_store.get("balance_sheet_ci"), theme=theme),
                                "pd-default-rate-trend-chart pd-default-rate-trend-chart-medium pd-default-rate-trend-chart-axis-room-medium",
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
                    _chart_surface(
                        "pd-balance-sheet-notching-trend-chart",
                        build_pd_notching_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, range_store.get("balance_sheet_notching"), theme=theme),
                        "pd-default-rate-trend-chart pd-notching-trend-chart",
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
                    _chart_surface(
                        "pd-balance-sheet-default-rate-trend-chart",
                        build_pd_default_rate_trend_figure(balance_sheet_performance_trend, monitoring_thresholds, range_store.get("balance_sheet_default_rate"), theme=theme),
                        "pd-default-rate-trend-chart pd-calibration-trend-chart",
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
                options={"note": f"Monitoring point {cq}"},
            ),
        ],
    )

    section_2_1 = _build_pd_post_review_overview(
        data, ctx, reporting_cycle, scenario, observations, rating_observations, cq, crr_scale,
    )

    section_2_2 = _build_pd_transition_matrix_section(data, ctx, reporting_cycle, theme, range_store)

    psi_performance_trend = build_pd_performance_trend_for_horizon(
        observations, rating_observations, cq, "1y", ctx, crr_scale,
    )
    psi_periods = get_pd_range_periods(ctx.quarters, cq)

    section_2_3 = html.Section(
        id="pd-population-stability-index",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.3 PSI", "PSI",
                "PSI based on IRB CRR key-driver stability, monitoring whether the performing-book population "
                "has shifted against the reference distribution.",
                "N/A", options={"show_rag": False},
            ),
            _build_psi_stability_summary(psi_performance_trend, thresholds, cq),
            html.Div(
                id="pd-psi-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Population Stability Index Trend",
                        "Quarter-by-quarter PSI for the selected population, with threshold bands and RAG-colored markers.",
                        "psi_trend",
                        psi_periods,
                        range_store.get("psi_trend"),
                    ),
                    dcc.Graph(
                        id="pd-psi-trend-chart",
                        figure=build_pd_psi_trend_figure(psi_performance_trend, monitoring_thresholds, cq, range_store.get("psi_trend"), theme=theme),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium",
                    ),
                ],
            ),
        ],
    )

    section_2_4 = _build_pd_scenario_ranking_section(data, ctx, reporting_cycle, theme, scenario_ranking_store)

    section_2_5 = _build_pd_sensitivity_section(data, ctx, reporting_cycle, theme, range_store)

    section_2_6 = _build_mev_range_section(data, ctx, range_store, mev_filter_store, theme_value=theme_value, reporting_cycle=reporting_cycle, scenario=scenario)

    chapter_2_body = html.Div(
        className="pd-chapter-body pd-chapter-body-secondary",
        children=[section_2_1, section_2_2, section_2_3, section_2_4, section_2_5, section_2_6],
    )

    _exec_style = (
        {
            "background": "linear-gradient(180deg, rgba(21,34,56,.96) 0%, rgba(17,28,47,.97) 100%)",
            "borderLeft": "3px solid #38bdf8",
            "borderRadius": "10px",
        }
        if theme == "dark" else
        {
            "background": "linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f8fafc 100%)",
            "borderLeft": "3px solid #2563eb",
            "borderRadius": "10px",
        }
    )
    executive_summary = html.Div(
        className="pd-performance-note",
        style=_exec_style,
        children=[
            html.Strong("Executive summary: "),
            "The PD Performance dashboard is the monitoring view for Probability of Default (PD) models "
            "across the wholesale portfolio. It tracks each model's calibration, discriminatory power, and "
            "population stability against agreed RAG thresholds, for both the ECL point-in-time and balance "
            "sheet horizons, and adds a post subjective review layer (transition migration, scenario rank "
            "ordering, sensitivity, and MEV range) so reviewers can judge whether model behaviour remains "
            "defensible across reporting cycles and stress scenarios.",
        ],
    )

    return [executive_summary, chapter_1, chapter_1_body, chapter_2, chapter_2_body]


# ---------------------------------------------------------------------------
# Default filter context + top-level layout
# ---------------------------------------------------------------------------


def _build_apply_button() -> html.Div:
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


def _build_top_bar(data: dict) -> html.Div:
    return html.Div(
        className="top-bar",
        children=[
            html.Div(
                style={"flex": "1"},
                children=[
                    html.Div(
                        "PD Performance Monitoring Dashboard",
                        className="monitoring-dashboard-title",
                    ),
                    build_global_filters(data, extra_controls=_build_apply_button()),
                ],
            ),
        ],
    )


def build_pd_apply_prompt() -> html.Section:
    """Executive summary + how-to guide shown until the user applies the filters."""
    return html.Section(
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    "The PD Performance dashboard is the monitoring view for Probability of Default (PD) models "
                    "across the wholesale portfolio. It tracks each model's calibration, discriminatory power, and "
                    "population stability against agreed RAG thresholds, for both the ECL point-in-time and balance "
                    "sheet horizons, and adds a post subjective review layer (transition migration, scenario rank "
                    "ordering, sensitivity, and MEV range) so reviewers can judge whether model behaviour remains "
                    "defensible across reporting cycles and stress scenarios.",
                ],
            ),
            html.Div(
                className="saas-model-panel-stack",
                children=[
                    html.Div(
                        className="section-card pd-mev-empty-state saas-getting-started",
                        children=[
                            html.Div("Getting started with the PD Performance dashboard", className="pd-mev-chart-title"),
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
                                            html.Span("1. Choose Reporting Cycle, Scenario, and Monitoring Point.", className="saas-getting-started-highlight"),
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
                                        html.Strong("Pick a Reporting Cycle. "),
                                        "Choose the cycle to review (e.g. CCAR 2026). This sets which monitoring points and "
                                        "precomputed metrics are available for every section.",
                                    ]),
                                    html.Li([
                                        html.Strong("Choose a Scenario. "),
                                        "Select the macro scenario (e.g. intsevere, baseline). The scenario drives the MEV "
                                        "Range section and the scenario-conditioned views.",
                                    ]),
                                    html.Li([
                                        html.Strong("Set the Monitoring Point. "),
                                        "Pick the as-of quarter for the snapshot. The available quarters follow the selected "
                                        "reporting cycle, and trends are shown up to this point.",
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
                                        html.Strong("Read the analysis in two chapters. "),
                                        "Once loaded, the dashboard is organised as:",
                                        html.Ul(
                                            className="saas-getting-started-substeps",
                                            children=[
                                                html.Li([
                                                    html.Strong("1. RAG Assignment — "),
                                                    "the core model-health view: overview, ECL PIT PD calibration conservatism, "
                                                    "discriminatory power, and balance sheet PD calibration.",
                                                ]),
                                                html.Li([
                                                    html.Strong("2. Post Subjective Review Analysis — "),
                                                    "qualitative deep-dives: transition matrix margins, population stability (PSI), "
                                                    "scenario rank ordering, sensitivity analysis, and MEV range.",
                                                ]),
                                            ],
                                        ),
                                    ]),
                                    html.Li([
                                        html.Strong("Fine-tune within each section. "),
                                        "Many charts have Window / From / To range controls and per-panel horizon toggles for "
                                        "on-screen analysis — these do not require re-applying the top filters.",
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


def build_stores() -> list:
    """``dcc.Store`` components backing this page's filter/range state.

    Rendered once in the shared app shell (:func:`shell.build_app_shell`) so
    they persist while navigating between pages.
    """
    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=TREND_HORIZON_STORE_ID, data=dict(DEFAULT_TREND_HORIZON_STORE)),
        dcc.Store(id=MEV_FILTER_STORE_ID, data=dict(DEFAULT_MEV_FILTER_STORE)),
        dcc.Store(id=SCENARIO_RANKING_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
    ]


def build_layout() -> list:
    """Registry entry point: build the page from the loaded dashboard data."""
    from ...data_access import PD_PERFORMANCE_DATA

    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Top bar + getting-started prompt.

    The dashboard content is rendered into ``CONTENT_ID`` only once the user
    clicks "Apply filters"; until then this getting-started guide is shown
    (mirroring the SAAS workspace).
    """
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
                            children=build_pd_apply_prompt(),
                        ),
                    ],
                ),
            ],
        ),
    ]
