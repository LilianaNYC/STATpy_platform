"""Layout for the Overview page: a cross-portfolio RAG command center.

Combines PD, LGD, EAD, and Loss into one view built directly on each tab's
own domain functions (see ``domain/overview.py``), organised as a single
chapter with five sections: RAG Assignment overview, Model RAG Heatmap,
RAG Trend Analysis, and Governance Summary.
"""

from __future__ import annotations

from collections import Counter
from textwrap import wrap
from urllib.parse import urlencode

import plotly.graph_objects as go
from dash import dcc, html

from .....shared.domain.calculations import filter_pd_periods_by_range, pd_tone_class
from .....shared.theme import normalize_theme_value
from .....shared.ui import controls as shared_filters
from .....shared.ui.charts import (
    _apply_transparent_background,
    _empty_figure,
    build_pd_time_series_xaxis,
)
from .....shared.ui.controls import build_chart_header
from .....shared.ui.loading import build_dashboard_loading_shell
from ...domain.overview import (
    FINAL_RAG_COLUMN,
    HEATMAP_COLUMNS,
    HEATMAP_FINAL_COLUMNS,
    MODEL_GROUPS,
    POST_SUBJECTIVE_COLUMNS,
    RAG_ASSIGNMENT_COLUMNS,
    RAG_COLUMNS,
    RAG_COLUMN_DESCRIPTIONS,
    REVIEW_FLOW_STAGES,
    available_periods,
    build_overview_rows,
    build_overview_segment_rows,
    display_rag,
    effective_rag,
    escalation_next_steps,
    heatmap_rows,
    overview_model_options,
    overview_summary,
    periods_through,
    resolve_current_rows,
    resolve_current_segment_rows,
    segment_heatmap_rows,
    segment_overview_summary,
    segment_top_findings,
    top_findings,
)
from .cards import build_pd_chapter_heading, build_pd_section_heading, pd_rag_dot
from .post_subjective import build_executive_summary

CONTENT_ID = "overview-content"
APPLY_FILTERS_ID = "overview-apply-filters"
APPLIED_FILTERS_STORE_ID = "overview-applied-filters-store"
REPORTING_CYCLE_ID = "overview-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "overview-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "overview-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "overview-reporting-cycle"
MONITORING_POINT_ID = "overview-monitoring-point"
MONITORING_POINT_TOGGLE_ID = "overview-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "overview-monitoring-point-menu"
MONITORING_POINT_FILTER_KEY = "overview-monitoring-point"
SEGMENT_MODEL_GROUP_ID = "overview-segment-model-group"
SEGMENT_MODEL_GROUP_TOGGLE_ID = "overview-segment-model-group-toggle"
SEGMENT_MODEL_GROUP_MENU_ID = "overview-segment-model-group-menu"
SEGMENT_MODEL_GROUP_FILTER_KEY = "overview-segment-model-group"
SEGMENT_MODEL_GROUP_OPTIONS = ["All", "PD", "LGD", "EAD", "Loss"]
OVERVIEW_MODEL_ID = "overview-model"
OVERVIEW_MODEL_SELECT_ALL_ID = "overview-model-select-all"
OVERVIEW_MODEL_TOGGLE_ID = "overview-model-toggle"
OVERVIEW_MODEL_MENU_ID = "overview-model-menu"
RAG_TREND_METRIC_ID = "overview-rag-trend-metric"
RAG_TREND_METRIC_TOGGLE_ID = "overview-rag-trend-metric-toggle"
RAG_TREND_METRIC_MENU_ID = "overview-rag-trend-metric-menu"
RAG_TREND_METRIC_FILTER_KEY = "overview-rag-trend-metric"
RAG_TREND_CHART_ID = "overview-rag-trend-chart"
SEGMENT_RAG_TREND_METRIC_ID = "overview-segment-rag-trend-metric"
SEGMENT_RAG_TREND_METRIC_TOGGLE_ID = "overview-segment-rag-trend-metric-toggle"
SEGMENT_RAG_TREND_METRIC_MENU_ID = "overview-segment-rag-trend-metric-menu"
SEGMENT_RAG_TREND_METRIC_FILTER_KEY = "overview-segment-rag-trend-metric"
SEGMENT_RAG_TREND_CHART_ID = "overview-segment-rag-trend-chart"
OVERVIEW_SUBNAV_ID = "overview-subnav"
RANGE_STORE_ID = "overview-range-store"
SCOPED_ROWS_STORE_ID = "overview-scoped-rows-store"
SEGMENT_SCOPED_ROWS_STORE_ID = "overview-segment-scoped-rows-store"
RAG_FLOW_SELECTION_STORE_ID = "overview-rag-flow-selection-store"
RAG_FLOW_MODEL_DESKTOP_ID = "overview-rag-flow-model-desktop"
RAG_FLOW_MODEL_COMPACT_ID = "overview-rag-flow-model-compact"
RAG_FLOW_SEGMENT_DESKTOP_ID = "overview-rag-flow-segment-desktop"
RAG_FLOW_SEGMENT_COMPACT_ID = "overview-rag-flow-segment-compact"
RAG_FLOW_MODEL_BROWSER_ID = "overview-rag-flow-model-browser"
RAG_FLOW_SEGMENT_BROWSER_ID = "overview-rag-flow-segment-browser"
RAG_FLOW_ENTITY_BUTTON_TYPE = "overview-rag-flow-entity-button"
RAG_FLOW_RESET_BUTTON_TYPE = "overview-rag-flow-reset-button"
RAG_FLOW_SHOW_ALL_BUTTON_TYPE = "overview-rag-flow-show-all-button"
RAG_TREND_RANGE_KEY = "overview_rag_trend"
SEGMENT_RAG_TREND_RANGE_KEY = "overview_segment_rag_trend"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
_RAG_FLOW_STAGES = [
    ("Overall RAG", "Performance RAG"),
    ("Post Subjective Review RAG", "Post Subjective Review RAG"),
    ("Pre Mitigation RAG", "Pre Mitigation RAG"),
    ("Post Mitigation RAG", "Post Mitigation RAG"),
]
# One definition per _RAG_FLOW_STAGES entry (same order) -- shared by the
# card-level "i" help chip and the Sankey chart's own HTML column headers
# (_rag_flow_column_headers).
_RAG_FLOW_STAGE_DEFINITIONS = [
    "Based on the results of tests applied at the modelled outcomes.",
    "Reflects the impact of any subjective overlays and considers the post-subjective review.",
    "Pre-Overlay RAG obtained from the trend of the post-subjective-review model RAG.",
    "Post-Overlay RAG based on the residual risk of the model, including compensating controls.",
]
_RAG_FLOW_TONE_ORDER = ("Green", "Amber", "Red", "N/A")
_RAG_FLOW_VALID_TONES = ("Green", "Amber", "Red")
_RAG_FLOW_BAND_RANGES = {
    "Green": (0.72, 0.90),
    "Amber": (0.41, 0.59),
    "Red": (0.10, 0.28),
    "N/A": (0.02, 0.07),
}
_RAG_FLOW_THEME_PALETTES = {
    "light": {
        "marker": {
            "Green": "#15803d",
            "Amber": "#d97706",
            "Red": "#dc2626",
            "N/A": "#64748b",
        },
        "label": {
            "Green": "#15803d",
            "Amber": "#b45309",
            "Red": "#b91c1c",
            "N/A": "#64748b",
        },
        "link": {
            "Green": "rgba(21,128,61,0.30)",
            "Amber": "rgba(217,119,6,0.32)",
            "Red": "rgba(220,38,38,0.32)",
            "N/A": "rgba(100,116,139,0.24)",
        },
        "band": {
            "Green": "rgba(21,128,61,0.09)",
            "Amber": "rgba(217,119,6,0.10)",
            "Red": "rgba(220,38,38,0.09)",
            "N/A": "rgba(100,116,139,0.07)",
        },
        "node_outline": "rgba(255,255,255,0.96)",
        "selected_outline": "#0284c7",
        "focus_text": "#0369a1",
        "divider": "rgba(100,116,139,0.34)",
    },
    "dark": {
        "marker": {
            "Green": "#22c55e",
            "Amber": "#f59e0b",
            "Red": "#ef4444",
            "N/A": "#94a3b8",
        },
        "label": {
            "Green": "#4ade80",
            "Amber": "#fbbf24",
            "Red": "#f87171",
            "N/A": "#cbd5e1",
        },
        "link": {
            "Green": "rgba(34,197,94,0.34)",
            "Amber": "rgba(245,158,11,0.36)",
            "Red": "rgba(239,68,68,0.36)",
            "N/A": "rgba(148,163,184,0.28)",
        },
        "band": {
            "Green": "rgba(34,197,94,0.14)",
            "Amber": "rgba(245,158,11,0.14)",
            "Red": "rgba(239,68,68,0.14)",
            "N/A": "rgba(148,163,184,0.09)",
        },
        "node_outline": "rgba(226,232,240,0.72)",
        "selected_outline": "#7dd3fc",
        "focus_text": "#7dd3fc",
        "divider": "rgba(148,163,184,0.28)",
    },
}


# ---------------------------------------------------------------------------
# Post Subjective Review sidecar
#
# Transition Matrix, Scenario Ranking, Sensitivity Analysis, and MEV Range
# are reporting-cycle-scoped (worst-case across the whole projection
# horizon), not quarter-conditioned, and their RAG logic lives in the view
# layer of each tab (pd_performance.py / post_subjective.py) rather than a
# domain module. Reusing those functions directly here -- a UI-to-UI import,
# consistent with how lgd_performance.py/ead_performance.py already reuse
# post_subjective.py -- keeps this page's promise that nothing is
# re-derived: the same functions each tab uses for real compute these too.
# ---------------------------------------------------------------------------


def _default_scenario(data: dict) -> str:
    from .....shared.repositories.filters_config import load_filter_config
    return load_filter_config()["scenarios"][0]["value"]


def _latest_scenario_by_key(rows: list[dict], group: str, key_fn) -> dict:
    """The saved Scenario (see loader.py's ``scenario`` column, surfaced onto
    rows as ``"Scenario"`` by ``_pd_review_flow_rags``/
    ``_review_flow_rags_from_metric_row``) for each ``key_fn(row)`` group's
    most recent quarter within ``rows``. MEV Range is reporting-cycle-scoped,
    not quarter-conditioned (see the module comment above), so this uses the
    scenario the *latest* reviewed quarter was actually saved under -- keys
    with no saved scenario at all (never reviewed) are omitted, and callers
    fall back to ``_default_scenario`` for those. ``key_fn`` lets callers
    group by (Model, Segment) (the Models chapter, and PD's Segments chapter,
    which resolve per model) or by Segment alone (LGD/EAD's Segments chapter,
    which already pools its Scenario Ranking/Sensitivity/MEV lookup across
    every model sharing a segment -- see augment_segment_rows_with_post_subjective)."""
    by_key: dict = {}
    for row in rows:
        if row["Model Group"] != group:
            continue
        by_key.setdefault(key_fn(row), []).append(row)
    result: dict = {}
    for key, key_rows in by_key.items():
        periods = available_periods(key_rows)
        if not periods:
            continue
        latest_row = next((row for row in key_rows if row["Monitoring Period"] == periods[-1]), None)
        scenario = str((latest_row or {}).get("Scenario", "") or "").strip()
        if scenario:
            result[key] = scenario
    return result


def _pd_post_subjective_rag(data: dict, models: set[str], segment: str, reporting_cycle: str, scenario: str) -> dict[str, str]:
    """``models`` is a set so the Segments chapter can pool every PD model
    when it needs a segment-level verdict, while the
    Models chapter passes a single-model set for its per-model verdict."""
    from .pd_performance import _pd_post_review_summaries
    from .....shared.domain.calculations import PdFilterContext, get_pd_crr_master_scale, set_precomputed_metrics

    cycle_data = (data.get("observations_by_cycle") or {}).get(reporting_cycle)
    if cycle_data:
        quarters = cycle_data["quarters"]
        performance_observations = cycle_data["performance_observations"]
        rating_migration_observations = cycle_data["rating_migration_observations"]
        metrics_store = cycle_data.get("metrics_store")
    else:
        quarters = data.get("quarters", [])
        performance_observations = data.get("performance_observations")
        rating_migration_observations = data.get("rating_migration_observations")
        metrics_store = None
    set_precomputed_metrics(metrics_store)

    cq = quarters[-1] if quarters else ""
    ctx = PdFilterContext(quarters=quarters, models=set(models), segment=segment, monitoring_point=cq)
    crr_scale = get_pd_crr_master_scale(data["monitoring_thresholds"])
    summaries = _pd_post_review_summaries(
        data, ctx, reporting_cycle, scenario,
        performance_observations, rating_migration_observations, cq, crr_scale,
    )
    by_name = {summary["name"]: summary for summary in summaries}

    def _rag(name: str) -> str:
        return by_name.get(name, {}).get("rag", "N/A")

    def _metric(name: str) -> str:
        return by_name.get(name, {}).get("metric", "—")

    return {
        "Transition Matrix RAG": _rag("Transition Matrix"),
        "Transition Matrix Metric": _metric("Transition Matrix"),
        "Scenario Ranking RAG": _rag("Scenario Ranking"),
        "Scenario Ranking Metric": _metric("Scenario Ranking"),
        "Sensitivity Analysis RAG": _rag("Sensitivity Analysis"),
        "Sensitivity Analysis Metric": _metric("Sensitivity Analysis"),
        "MEV Range RAG": _rag("MEV Range"),
        "MEV Range Metric": _metric("MEV Range"),
        # The scenario actually used to compute MEV Range above (the row's own
        # saved scenario, or the portfolio-wide default when never reviewed --
        # see _latest_scenario_by_key) -- surfaced separately from "Scenario"
        # (the raw saved value, which can be empty) so callers always have a
        # value to show, e.g. in a hover tooltip or escalation card.
        "MEV Range Scenario": scenario,
    }


def _lgd_ead_post_subjective_rag(data: dict, model_type: str, sensitivity_key: str, entity: str, reporting_cycle: str, scenario: str, level: str = "model", model_segment: str = "All", segment_model: str | None = None) -> dict[str, str]:
    """``entity`` is a model name when ``level == "model"`` (Models chapter),
    or a segment name when ``level == "segment"``
    (Segments chapter) -- mirrors the ``(model, segment)`` scoping each tab's
    own sensitivity-projections and MEV catalog already support. ``model_segment``
    is the real segment to use for the ``level == "model"`` case when the model
    has no ``All`` aggregate row (see ``_chapter1_model_metric_rows``) -- the
    Chapter 1 row itself is already standing in for that model's single real
    segment, so its subjective-review columns must resolve against the same
    segment. ``segment_model`` is the real owning model to use for the
    ``level == "segment"`` case -- more than one model can own the same
    segment name (e.g. both LGD Model A and LGD Model B have "O&M"), so this
    must be the specific model the Segments-chapter row is actually showing,
    not a fixed stand-in model; defaults to ``f"{model_type} Model A"`` only
    when the caller doesn't know the real model."""
    from .post_subjective import (
        PostSubjectiveConfig, _fmt_pct, _impact_summary, _mev_range_summary, _projection_rows,
        _scenario_ranking_summary, _sensitivity_threshold, resolve_scenario_selection,
    )

    cfg = PostSubjectiveConfig(
        prefix=model_type.lower(), label=model_type, model_type=model_type,
        sensitivity_key=sensitivity_key, scenario_filter_id="overview-unused",
    )
    model, segment = (entity, model_segment) if level == "model" else (segment_model or f"{model_type} Model A", entity)
    all_rows = _projection_rows(data.get(sensitivity_key) or [], reporting_cycle, model, segment)
    if all_rows:
        selected = resolve_scenario_selection(all_rows, None)
        rank = _scenario_ranking_summary([row for row in all_rows if row.get("scenario_variant") in selected])
        scenario_ranking_rag = "Green" if rank["status"] == "Ranking maintained" else "Red"
        scenario_ranking_metric = rank["status"]
        threshold = _sensitivity_threshold(data.get("monitoring_thresholds") or {}, model_type)
        impact = _impact_summary([row for row in all_rows if row.get("scenario_variant") in {"baseline", "baseline_2std_shock"}], threshold)
        sensitivity_rag = {"green": "Green", "red": "Red"}.get(impact["tone"], "N/A")
        sensitivity_metric = _fmt_pct(impact["max_impact"])
    else:
        scenario_ranking_rag = "N/A"
        scenario_ranking_metric = "—"
        sensitivity_rag = "N/A"
        sensitivity_metric = "—"
    if level == "segment":
        mev_summary = _mev_range_summary(cfg, data, model, entity, reporting_cycle, scenario)
    else:
        mev_summary = _mev_range_summary(cfg, data, entity, segment, reporting_cycle, scenario)
    return {
        "Transition Matrix RAG": "N/A",
        "Transition Matrix Metric": "—",
        "Scenario Ranking RAG": scenario_ranking_rag,
        "Scenario Ranking Metric": scenario_ranking_metric,
        "Sensitivity Analysis RAG": sensitivity_rag,
        "Sensitivity Analysis Metric": sensitivity_metric,
        "MEV Range RAG": mev_summary["rag"],
        "MEV Range Metric": mev_summary["metric"],
        "MEV Range Scenario": scenario,  # see the matching comment on _pd_post_subjective_rag
    }


def augment_rows_with_post_subjective(rows: list[dict], data: dict, reporting_cycle: str) -> list[dict]:
    """Merge Transition Matrix / Scenario Ranking / Sensitivity / MEV Range RAG onto
    each row, keyed by (Model Group, Model, Segment) so every quarter row for a
    given model within this reporting cycle carries the same cycle-level verdict."""
    def _model_segment_key(row: dict) -> tuple[str, str]:
        return row["Model"], row.get("Segment", "All")

    default_scenario = _default_scenario(data)
    pd_scenarios = _latest_scenario_by_key(rows, "PD", _model_segment_key)
    lgd_scenarios = _latest_scenario_by_key(rows, "LGD", _model_segment_key)
    ead_scenarios = _latest_scenario_by_key(rows, "EAD", _model_segment_key)
    sidecar: dict[tuple[str, str, str], dict[str, str]] = {}

    pd_keys = {(row["Model"], row.get("Segment", "All")) for row in rows if row["Model Group"] == "PD"}
    for model, segment in pd_keys:
        # ctx uses lowercase "all" for the pooled/Segment: All case, matching
        # the PD Performance tab's own convention (see _ctx_store_keys).
        ctx_segment = "all" if segment == "All" else segment
        models = {model}
        scenario = pd_scenarios.get((model, segment), default_scenario)
        sidecar[("PD", model, segment)] = _pd_post_subjective_rag(data, models, ctx_segment, reporting_cycle, scenario)
    # Sourced from ``rows`` itself so the sidecar stays aligned with whatever
    # model rows the Overview page is currently surfacing for LGD and EAD --
    # including a model's real segment when it's standing in for a missing
    # ``All`` aggregate row (see ``_chapter1_model_metric_rows``).
    lgd_keys = {(row["Model"], row.get("Segment", "All")) for row in rows if row["Model Group"] == "LGD"}
    ead_keys = {(row["Model"], row.get("Segment", "All")) for row in rows if row["Model Group"] == "EAD"}
    for model, segment in lgd_keys:
        scenario = lgd_scenarios.get((model, segment), default_scenario)
        sidecar[("LGD", model, segment)] = _lgd_ead_post_subjective_rag(data, "LGD", "lgd_sensitivity_projections", model, reporting_cycle, scenario, model_segment=segment)
    for model, segment in ead_keys:
        scenario = ead_scenarios.get((model, segment), default_scenario)
        sidecar[("EAD", model, segment)] = _lgd_ead_post_subjective_rag(data, "EAD", "ead_sensitivity_projections", model, reporting_cycle, scenario, model_segment=segment)

    for row in rows:
        key = (row["Model Group"], row["Model"], row.get("Segment", "All"))
        row.update(sidecar.get(key, {}))
    return rows


def augment_segment_rows_with_post_subjective(rows: list[dict], data: dict, reporting_cycle: str) -> list[dict]:
    """Segments-chapter equivalent of ``augment_rows_with_post_subjective``,
    keyed by (Model Group, Model, Segment): more than one PD model can own the
    same segment name (e.g. both PD Model A and PD Model B have "Cyclical"),
    and _pd_segment_rows already disambiguates by model, so this looks up
    each row's Post Subjective Review data (Transition Matrix, Scenario
    Ranking, Sensitivity Analysis, MEV Range) scoped to that single model
    too -- previously it pooled every PD model sharing the segment, which
    made a row labelled e.g. "PD Model B - Cyclical" show a MEV Range count
    that actually spanned every Cyclical-owning model, not just Model B.
    LGD/EAD look up their own per-segment sensitivity/MEV data directly (see
    _lgd_ead_post_subjective_rag's ``level="segment"``). Loss has no Post
    Subjective Review columns, so it's left out entirely."""
    def _model_segment_key(row: dict) -> tuple[str, str]:
        return row["Model"], row["Segment"]

    default_scenario = _default_scenario(data)
    pd_scenarios = _latest_scenario_by_key(rows, "PD", _model_segment_key)
    # LGD/EAD pool their Scenario Ranking/Sensitivity/MEV lookup across every
    # model sharing a segment (one result reused for all of them, see below),
    # so the saved scenario is likewise resolved per Segment alone here, not
    # per (Model, Segment).
    lgd_scenarios = _latest_scenario_by_key(rows, "LGD", lambda row: row["Segment"])
    ead_scenarios = _latest_scenario_by_key(rows, "EAD", lambda row: row["Segment"])
    sidecar: dict[tuple[str, str, str], dict[str, str]] = {}
    for model, segment in {(row["Model"], row["Segment"]) for row in rows if row["Model Group"] == "PD"}:
        scenario = pd_scenarios.get((model, segment), default_scenario)
        sidecar[("PD", model, segment)] = _pd_post_subjective_rag(data, {model}, segment, reporting_cycle, scenario)
    for segment in {row["Segment"] for row in rows if row["Model Group"] == "LGD"}:
        scenario = lgd_scenarios.get(segment, default_scenario)
        result = _lgd_ead_post_subjective_rag(data, "LGD", "lgd_sensitivity_projections", segment, reporting_cycle, scenario, level="segment")
        for model in {row["Model"] for row in rows if row["Model Group"] == "LGD" and row["Segment"] == segment}:
            sidecar[("LGD", model, segment)] = result
    for segment in {row["Segment"] for row in rows if row["Model Group"] == "EAD"}:
        scenario = ead_scenarios.get(segment, default_scenario)
        result = _lgd_ead_post_subjective_rag(data, "EAD", "ead_sensitivity_projections", segment, reporting_cycle, scenario, level="segment")
        for model in {row["Model"] for row in rows if row["Model Group"] == "EAD" and row["Segment"] == segment}:
            sidecar[("EAD", model, segment)] = result
    for row in rows:
        row.update(sidecar.get((row["Model Group"], row.get("Model", ""), row["Segment"]), {}))
    return rows


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------


def _dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _rag_trend_dropdown_options(values: list[str]) -> list[dict[str, str]]:
    return [
        {
            "label": "Performance RAG" if value == "Overall RAG" else value,
            "value": value,
        }
        for value in values
    ]


def _build_filter(label: str, component) -> html.Div:
    return html.Div(className="monitoring-filter", children=[html.Label(label), component])


def model_toggle_label(value: list[str] | None, options: list[dict] | None) -> str:
    """Summarize the Model checkbox dropdown's selection for its toggle button,
    mirroring SAAS workspace's own Model Name toggle label."""
    values = list(value or [])
    option_values = [option["value"] for option in (options or [])]
    if not values:
        return "Select models"
    if option_values and set(values) == set(option_values):
        return "All"
    if len(values) == 1:
        return values[0]
    return f"{len(values)} models selected"


def _build_model_filter(options: list[dict], value: list[str]) -> html.Div:
    all_checked = bool(options) and set(value) == {option["value"] for option in options}
    return html.Div(
        className="checkbox-dropdown",
        children=[
            html.Button(
                model_toggle_label(value, options),
                id=OVERVIEW_MODEL_TOGGLE_ID,
                type="button",
                n_clicks=0,
                className="checkbox-dropdown-toggle",
            ),
            html.Div(
                id=OVERVIEW_MODEL_MENU_ID,
                className="checkbox-dropdown-menu",
                children=[
                    dcc.Checklist(
                        id=OVERVIEW_MODEL_SELECT_ALL_ID,
                        options=[{"label": "All", "value": "all"}],
                        value=["all"] if all_checked else [],
                        className="pd-models-select-all",
                    ),
                    dcc.Checklist(
                        id=OVERVIEW_MODEL_ID,
                        options=options,
                        value=list(value),
                        className="pd-models-checklist",
                    ),
                ],
            ),
        ],
    )


def _subnav_link(section_id: str, label: str, active: bool = False) -> html.Button:
    return html.Button(
        label,
        type="button",
        className="active" if active else "",
        **{"data-pd-subnav-target": section_id, "aria-current": "location" if active else "false"},
    )


def _build_overview_subnav() -> html.Div:
    return html.Div(
        id=OVERVIEW_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-overview active",
                children=[
                    html.Div("Models", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-summary", "Model Overview", active=True),
                            _subnav_link("overview-heatmap", "Model RAG Heatmap"),
                            _subnav_link("overview-rag-trend", "Model RAG Trend Analysis"),
                            _subnav_link("overview-governance-summary", "Model Governance Summary"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group pd-subnav-group-rag",
                children=[
                    html.Div("Segments", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-segment-summary", "Segment Overview"),
                            _subnav_link("overview-segment-heatmap", "Segment RAG Heatmap"),
                            _subnav_link("overview-segment-rag-trend", "Segment RAG Trend Analysis"),
                            _subnav_link("overview-segment-governance-summary", "Segment Governance Summary"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _hero_kpi(
    value, label: str, rag: str | None = None, description: str | None = None,
    items: list[str | tuple[str, str]] | None = None,
) -> html.Div:
    tone = effective_rag(rag).lower() if rag else "neutral"
    main = [
        html.Div(str(value), className="overview-hero-kpi-value"),
        html.Div(label, className="overview-hero-kpi-label"),
    ]
    if description:
        main.append(html.Div(description, className="overview-hero-kpi-description"))

    if items:
        list_children = []
        for item in items:
            if isinstance(item, tuple):
                text, item_tone = item
                list_children.append(html.Span(text, className=f"overview-hero-kpi-list-item overview-hero-kpi-list-item-{item_tone}"))
            else:
                list_children.append(html.Span(item, className="overview-hero-kpi-list-item"))
        return html.Div(
            className=f"overview-hero-kpi overview-hero-kpi-{tone} overview-hero-kpi-with-list",
            children=[
                html.Div(main, className="overview-hero-kpi-main"),
                html.Div(list_children, className="overview-hero-kpi-list"),
            ],
        )
    return html.Div(className=f"overview-hero-kpi overview-hero-kpi-{tone}", children=main)


# ---------------------------------------------------------------------------
# Charts
#
# dcc.Graph defaults to an inline ``style="height:100%; width:100%"`` unless
# a ``style`` is passed explicitly. With no fixed-height ancestor, that
# resolves against an indeterminate parent and Plotly's ``responsive: true``
# then squashes the chart to whatever tiny size it ends up measuring instead
# of the figure's own declared ``layout.height``. Every chart below has a
# matching ``*_height`` helper so its ``dcc.Graph`` can be given an explicit
# ``style={"height": ...}`` that actually matches the figure.
# ---------------------------------------------------------------------------

def heatmap_chart_height(rows: list[dict]) -> int:
    # Post Subjective Review metric cells can wrap onto two lines (e.g.
    # "Ranking maintained"), so rows need extra height to fit that second line.
    return max(240, 70 + 60 * len(rows))


def _wrap_metric_text(metric: str, max_len: int = 10) -> str:
    """Break long metric text (e.g. "Ranking maintained") onto two lines at a
    word boundary so it fits the narrower cells of the side-by-side heatmap
    panels instead of overflowing into the next column."""
    if len(metric) <= max_len or " " not in metric:
        return metric
    words = metric.split(" ")
    mid = len(words) // 2
    return " ".join(words[:mid]) + "<br>" + " ".join(words[mid:])


def _normalize_rag_flow_tone(value: str | None) -> str:
    rag = display_rag(value)
    return rag if rag in _RAG_FLOW_TONE_ORDER else "N/A"


def _rag_flow_palette(theme: str) -> dict[str, object]:
    return _RAG_FLOW_THEME_PALETTES["dark" if theme == "dark" else "light"]


def _rag_flow_entity_label(row: dict, entity_kind: str = "model") -> str:
    group = str(row.get("Model Group", "") or "").strip()
    model = str(row.get("Model", "") or "").strip()
    segment = str(row.get("Segment", "") or "").strip()
    # The Segments chapter combines model + segment because more than one
    # model within a group can cover the same segment name, so the pair
    # disambiguates which model's data a row shows. The Models chapter has
    # one row per model regardless of which segment (if any) it's standing in
    # for -- e.g. a model whose Chapter 1 row falls back to its one real
    # segment because it has no "All" aggregate row (see
    # _chapter1_model_metric_rows) still reads as just that model's name.
    if entity_kind == "segment" and segment and segment != "All":
        entity = f"{model} · {segment}" if model else segment
    else:
        entity = model
    if group and entity and not entity.lower().startswith(group.lower()):
        return f"{group} {entity}"
    return entity or group


def _wrap_rag_flow_label(label: str, max_chars: int) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    parts = wrap(text, width=max_chars, break_long_words=True, break_on_hyphens=True)
    return "<br>".join(parts)


def _rag_flow_chart_height(flow_rows: list[dict[str, object]], compact: bool = False) -> int:
    # The default chart is aggregated by RAG bucket, so its height should not
    # grow with the number of models in scope. Model names live in the
    # scrollable journey browser and only the selected path is labelled.
    return 480 if compact else 460


def _rag_flow_models(current_rows: list[dict], entity_kind: str = "model") -> list[dict[str, object]]:
    flow_rows: list[dict[str, object]] = []
    for row in current_rows:
        entity_label = _rag_flow_entity_label(row, entity_kind)
        if not entity_label:
            continue
        if row.get("Model Group") == "Loss":
            # Loss has no review/mitigation pipeline -- there's nothing in
            # "Post Subjective Review RAG" / "Pre Mitigation RAG" / "Post
            # Mitigation RAG" to read, so its Overall (Performance) RAG
            # carries flat through all four stages instead of being dropped
            # from the journey entirely (mirrors how
            # _final_post_mitigation_distribution_card folds Loss into the
            # Final RAG buckets using the same value).
            overall_tone = _normalize_rag_flow_tone(row.get("Overall RAG"))
            tones = [overall_tone] * len(_RAG_FLOW_STAGES)
        else:
            tones = [_normalize_rag_flow_tone(row.get(column)) for column, _ in _RAG_FLOW_STAGES]
        # A journey is only displayed when all four stages are explicitly
        # available. Missing or unrecognised values are not promoted into an
        # inferred N/A path.
        if any(tone not in _RAG_FLOW_VALID_TONES for tone in tones):
            continue
        flow_rows.append({
            "Model Group": row.get("Model Group", ""),
            "Model": row.get("Model", ""),
            "Entity Label": entity_label,
            "Monitoring Period": row.get("Monitoring Period", ""),
            "tones": tones,
        })
    return flow_rows


def _rag_flow_visible_stages(row: dict[str, object]) -> list[tuple[tuple[str, str], str]]:
    """Which (stage, tone) pairs the entity browser shows for one journey row.

    Loss's row carries its Overall RAG flat across all four ``tones`` slots
    so it still counts toward the Sankey's stage totals and the Final RAG
    buckets (see ``_rag_flow_models``), but repeating that single value as
    four identical chips would misrepresent it as having gone through a
    review/mitigation pipeline it doesn't have -- so its row only displays
    the first (Performance RAG) stage.
    """
    stages = list(zip(_RAG_FLOW_STAGES, row["tones"]))
    return stages[:1] if row.get("Model Group") == "Loss" else stages


def _rag_flow_summary(flow_rows: list[dict[str, object]]) -> dict[str, int]:
    known_scale = {"Green": 1, "Amber": 2, "Red": 3, "N/A": 2}
    escalated_after_review = 0
    final_non_green = 0
    improved_to_final = 0
    by_group = Counter()

    for row in flow_rows:
        tones = row["tones"]
        if not isinstance(tones, list) or len(tones) != len(_RAG_FLOW_STAGES):
            continue
        by_group[str(row.get("Model Group", "") or "Unknown")] += 1
        if known_scale.get(tones[1], 2) > known_scale.get(tones[0], 2):
            escalated_after_review += 1
        if tones[3] != "Green":
            final_non_green += 1
        if known_scale.get(tones[3], 2) < known_scale.get(tones[0], 2):
            improved_to_final += 1

    return {
        "models": len(flow_rows),
        "escalated_after_review": escalated_after_review,
        "final_non_green": final_non_green,
        "improved_to_final": improved_to_final,
        "pd_models": by_group.get("PD", 0),
        "lgd_models": by_group.get("LGD", 0),
        "ead_models": by_group.get("EAD", 0),
        "loss_models": by_group.get("Loss", 0),
    }


def _rag_flow_selection_rows(
    flow_rows: list[dict[str, object]],
    selection: dict[str, object] | None,
) -> list[dict[str, object]]:
    if not selection or selection.get("all"):
        return flow_rows
    try:
        stage_index = int(selection.get("stage_index", -1))
    except (TypeError, ValueError):
        return flow_rows
    tone = str(selection.get("tone", "") or "")
    if stage_index not in range(len(_RAG_FLOW_STAGES)) or tone not in _RAG_FLOW_VALID_TONES:
        return flow_rows
    return [
        row
        for row in flow_rows
        if isinstance(row.get("tones"), list)
        and len(row["tones"]) == len(_RAG_FLOW_STAGES)
        and row["tones"][stage_index] == tone
    ]


def _rag_flow_entity_browser(
    current_rows: list[dict],
    selection: dict[str, object] | None,
    entity_kind: str,
) -> html.Div:
    flow_rows = _rag_flow_models(current_rows, entity_kind)
    selected_rows = _rag_flow_selection_rows(flow_rows, selection)
    scope = "segment" if entity_kind == "segment" else "model"
    entity_label = "segment" if scope == "segment" else "model"

    if not selection:
        return html.Div(
            className="overview-rag-flow-browser-empty",
            children=[
                html.Span("Explore the journey", className="overview-rag-flow-browser-kicker"),
                html.Strong("Select any RAG count in the chart"),
                html.P(
                    f"The chart will focus on that bucket and open a scrollable list of {entity_label} journeys below."
                ),
                html.Button(
                    f"See all {len(flow_rows)} {entity_label}{'' if len(flow_rows) == 1 else 's'}",
                    id={"type": RAG_FLOW_SHOW_ALL_BUTTON_TYPE, "scope": scope},
                    n_clicks=0,
                    type="button",
                    className="overview-rag-flow-show-all",
                ) if flow_rows else None,
            ],
        )

    is_all = bool(selection.get("all"))
    active_entity = str(selection.get("entity", "") or "")
    ordered_rows = sorted(selected_rows, key=lambda row: str(row.get("Entity Label", "")).lower())
    periods = sorted({
        str(row.get("Monitoring Period", "") or "").strip()
        for row in ordered_rows
        if str(row.get("Monitoring Period", "") or "").strip()
    })
    period_copy = periods[0] if len(periods) == 1 else (", ".join(periods) if periods else "current selection")

    if is_all:
        heading_title = f"All {entity_label}s"
        heading_copy = (
            f"Every complete {entity_label} journey in the current filtered data. "
            f"Select a {entity_label} below to highlight its recorded path, or click a RAG count in the chart to focus one bucket."
        )
    else:
        stage_index = int(selection.get("stage_index", 0))
        tone = str(selection.get("tone", "N/A"))
        heading_title = f"{_RAG_FLOW_STAGES[stage_index][1]} · {tone}"
        heading_copy = (
            f"Only complete journeys available in the current filtered data are shown. "
            f"Select a {entity_label} below to highlight its recorded path."
        )

    heading_actions = []
    if not is_all and flow_rows:
        heading_actions.append(
            html.Button(
                f"See all {len(flow_rows)} {entity_label}s",
                id={"type": RAG_FLOW_SHOW_ALL_BUTTON_TYPE, "scope": scope},
                n_clicks=0,
                type="button",
                className="overview-rag-flow-show-all",
            )
        )
    heading_actions.append(
        html.Button(
            "Back to portfolio view",
            id={"type": RAG_FLOW_RESET_BUTTON_TYPE, "scope": scope},
            n_clicks=0,
            type="button",
            className="overview-rag-flow-reset",
        )
    )

    return html.Div(
        className="overview-rag-flow-browser-panel",
        children=[
            html.Div(
                className="overview-rag-flow-browser-heading",
                children=[
                    html.Div(
                        children=[
                            html.Span(
                                f"{len(ordered_rows)} {entity_label}{'' if len(ordered_rows) == 1 else 's'} · {period_copy}",
                                className="overview-rag-flow-browser-kicker",
                            ),
                            html.Strong(heading_title),
                            html.P(heading_copy),
                        ],
                    ),
                    html.Div(heading_actions, className="overview-rag-flow-browser-actions"),
                ],
            ),
            html.Div(
                className="overview-rag-flow-entity-list",
                children=[
                    html.Button(
                        id={
                            "type": RAG_FLOW_ENTITY_BUTTON_TYPE,
                            "scope": scope,
                            "entity": str(row.get("Entity Label", "")),
                        },
                        n_clicks=0,
                        type="button",
                        className=(
                            "overview-rag-flow-entity-row overview-rag-flow-entity-row-active"
                            if str(row.get("Entity Label", "")) == active_entity
                            else "overview-rag-flow-entity-row"
                        ),
                        children=[
                            html.Span(str(row.get("Entity Label", "")), className="overview-rag-flow-entity-name"),
                            html.Span(
                                className="overview-rag-flow-entity-journey",
                                children=[
                                    html.Span(
                                        className=f"overview-rag-flow-journey-stage overview-rag-flow-journey-{tone_value.lower().replace('/', '-')}",
                                        title=f"{stage_name}: {tone_value}",
                                        children=[
                                            html.Small(stage_name),
                                            html.Strong(tone_value),
                                        ],
                                    )
                                    for (_, stage_name), tone_value in _rag_flow_visible_stages(row)
                                ],
                            ),
                        ],
                    )
                    for row in ordered_rows
                ],
            ),
        ],
    )


def _chapter1_gap_card(exclusions: list[dict]) -> html.Div | None:
    """List card for models Chapter 1 had to drop -- 2+ real segments but no
    "All" aggregate row, so there's no single row to represent them (see
    _pd_chapter1_scope / _chapter1_model_metric_rows in domain/overview.py).
    Same value/label/list inner layout as its neighbours in this row (Models
    monitored, Final Red/Amber/Green -- see _hero_kpi), just with a dashed
    neutral border (borrowed from the PD/LGD/EAD Performance tabs' "Chapter 2"
    RAG-lifecycle card) instead of a solid RAG-tinted one, since this card is
    a data-gap notice rather than a RAG bucket. No RAG dot on the list items --
    there's no per-model red/amber/green assessment to show here, so a dot
    would just be decorative and imply a status judgement that doesn't exist.
    Reuses existing theme-aware classes throughout, so no new dark-mode rules
    are needed."""
    if not exclusions:
        return None
    tooltip = "Segment data exists but there's no portfolio-wide (e.g. All) aggregate to summarize in this section."
    return html.Div(
        className="overview-hero-kpi overview-hero-kpi-neutral overview-hero-kpi-with-list overview-hero-kpi-dashed",
        children=[
            html.Div(
                [
                    html.Div(str(len(exclusions)), className="overview-hero-kpi-value"),
                    html.Div(
                        [
                            "Models excluded",
                            html.Span(
                                "?", className="pd-info-chip overview-hero-kpi-info-chip", role="img",
                                **{"aria-label": tooltip, "title": tooltip},
                            ),
                        ],
                        className="overview-hero-kpi-label",
                    ),
                ],
                className="overview-hero-kpi-main",
            ),
            html.Div(
                [
                    html.Span(
                        f"{item['Model']} ({', '.join(item['Segments'])})",
                        className="overview-hero-kpi-list-item",
                    )
                    for item in exclusions
                ],
                className="overview-hero-kpi-list",
            ),
        ],
    )


def _final_post_mitigation_distribution_card(
    current_rows: list[dict], entity_kind: str = "model", exclusions: list[dict] | None = None,
) -> html.Div:
    is_segment = entity_kind == "segment"
    summary = segment_overview_summary(current_rows) if is_segment else overview_summary(current_rows)
    # Loss has no review/mitigation pipeline, so _rag_flow_models carries its
    # Overall (Performance) RAG flat through all four stages instead of
    # dropping it from the journey -- that flat tone is what lands in
    # tones[3] here too, so Loss folds into the same Red/Amber/Green buckets
    # as everything else with no special-casing needed.
    flow_rows = _rag_flow_models(current_rows, entity_kind)
    final_models = {"Red": [], "Amber": [], "Green": [], "N/A": []}
    for row in flow_rows:
        tones = row["tones"]
        if not isinstance(tones, list) or len(tones) != len(_RAG_FLOW_STAGES):
            continue
        final_models.setdefault(tones[3], []).append(str(row.get("Entity Label", "")))

    def _ordered_unique(labels: list[str]) -> list[str]:
        return sorted(dict.fromkeys(label for label in labels if label))

    red_models = _ordered_unique(final_models["Red"])
    amber_models = _ordered_unique(final_models["Amber"])
    green_models = _ordered_unique(final_models["Green"])

    kpis = [
        _hero_kpi(
            summary["segments"] if is_segment else summary["models"],
            "Segments monitored" if is_segment else "Models monitored",
            "blue",
            description="Across every model group" if is_segment else "Across PD, LGD, EAD, and Loss",
        ),
        _hero_kpi(len(red_models), "Final Red", "Red", items=red_models or ["None in scope"]),
        _hero_kpi(len(amber_models), "Final Amber", "Amber", items=amber_models or ["None in scope"]),
        _hero_kpi(len(green_models), "Final Green", "Green", items=green_models or ["None in scope"]),
    ]
    gap_card = _chapter1_gap_card(exclusions)
    if gap_card is not None:
        kpis.append(gap_card)

    kpis_class = "overview-hero-kpis overview-summary-kpis" + ("" if exclusions else " overview-summary-kpis-quad")
    return html.Div(
        className="section-card overview-summary-final-post-mitigation",
        children=[
            build_chart_header(
                "Post Mitigation Distribution",
                "Post Mitigation is treated as the final portfolio outcome for models with review coverage; Loss's "
                "Overall RAG (performance-only) is folded into the same buckets.",
            ),
            html.Div(className=kpis_class, children=kpis),
        ],
    )


def _rag_flow_summary_card(current_rows: list[dict], theme: str, entity_kind: str = "model") -> html.Div:
    rag_flow_summary = _rag_flow_summary(_rag_flow_models(current_rows, entity_kind))
    is_segment = entity_kind == "segment"
    entity_label = "segment" if is_segment else "model"
    entity_label_plural = "segments" if is_segment else "models"
    header_copy = (
        "Segments flowing from performance through review and mitigation layers for the selected monitoring point."
        if is_segment
        else "Models flowing from performance through review and mitigation layers for the selected monitoring point."
    )
    title = "Segment RAG Migration Journey" if is_segment else "RAG Migration Journey"
    desktop_graph_id = RAG_FLOW_SEGMENT_DESKTOP_ID if is_segment else RAG_FLOW_MODEL_DESKTOP_ID
    compact_graph_id = RAG_FLOW_SEGMENT_COMPACT_ID if is_segment else RAG_FLOW_MODEL_COMPACT_ID
    browser_id = RAG_FLOW_SEGMENT_BROWSER_ID if is_segment else RAG_FLOW_MODEL_BROWSER_ID
    return html.Div(
        className="section-card overview-summary-rag-flow",
        children=[
            build_chart_header(title, header_copy),
            html.Div(
                className="overview-rag-flow-graphs",
                children=[
                    html.Div(
                        className="overview-rag-flow-graph-desktop",
                        children=[
                            _rag_flow_column_headers(),
                            dcc.Graph(
                                id=desktop_graph_id,
                                className="overview-rag-flow-graph",
                                figure=_rag_flow_sankey_figure(current_rows, theme, entity_kind=entity_kind),
                                config=_GRAPH_CONFIG,
                                style={"height": f"{_rag_flow_chart_height(_rag_flow_models(current_rows, entity_kind))}px"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-rag-flow-graph-compact",
                        children=[
                            _rag_flow_column_headers(compact=True),
                            dcc.Graph(
                                id=compact_graph_id,
                                className="overview-rag-flow-graph",
                                figure=_rag_flow_sankey_figure(current_rows, theme, compact=True, entity_kind=entity_kind),
                                config=_GRAPH_CONFIG,
                                style={"height": f"{_rag_flow_chart_height(_rag_flow_models(current_rows, entity_kind), compact=True)}px"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                id=browser_id,
                className="overview-rag-flow-browser",
                children=_rag_flow_entity_browser(current_rows, None, entity_kind),
            ),
            html.Div(
                className="overview-review-focus",
                children=[
                    html.Div([
                        html.Span(f"{entity_label_plural.title()} in flow"),
                        html.Strong(
                            f"{rag_flow_summary['models']} {entity_label_plural} carried into the journey "
                            f"({rag_flow_summary['pd_models']} PD, {rag_flow_summary['lgd_models']} LGD, "
                            f"{rag_flow_summary['ead_models']} EAD, {rag_flow_summary['loss_models']} Loss)"
                        ),
                    ]),
                    html.Div([
                        html.Span("Escalated after review"),
                        html.Strong(
                            f"{rag_flow_summary['escalated_after_review']} {entity_label}(s) worsened between Performance and Post Subjective Review"
                        ),
                    ]),
                    html.Div([
                        html.Span("Final Amber / Red"),
                        html.Strong(
                            f"{rag_flow_summary['final_non_green']} {entity_label}(s) still finish Amber or Red after mitigation"
                        ),
                    ]),
                    html.Div([
                        html.Span("Improved to final"),
                        html.Strong(
                            f"{rag_flow_summary['improved_to_final']} {entity_label}(s) finished better than they started"
                        ),
                    ]),
                ],
            ),
        ],
    )


def _rag_flow_sankey_figure(
    current_rows: list[dict],
    theme: str,
    compact: bool = False,
    selection: dict[str, object] | None = None,
    entity_kind: str = "model",
) -> go.Figure:
    flow_rows = _rag_flow_models(current_rows, entity_kind)
    height = _rag_flow_chart_height(flow_rows, compact=compact)
    if not flow_rows:
        return _empty_figure("No review-to-mitigation flow data is available for the selected filters.", height=height, theme=theme)

    selected_rows = _rag_flow_selection_rows(flow_rows, selection)
    entity_label = "segment" if entity_kind == "segment" else "model"
    is_dark = theme == "dark"
    palette = _rag_flow_palette(theme)
    marker_colors = palette["marker"]
    label_colors = palette["label"]
    link_colors = palette["link"]
    band_colors = palette["band"]
    text_color = "#e2e8f0" if is_dark else "#0f172a"
    stage_positions = [0.24, 1.12, 2.0, 2.88] if compact else [0.18, 1.08, 1.98, 2.88]
    tone_font_size = 13 if compact else 15
    left_label_room = 0.66 if compact else 0.72
    right_label_room = 0.42 if compact else 0.48
    # Stage column labels/tooltips now render as an HTML header row above the
    # chart (see _rag_flow_column_headers), matching the Model RAG Heatmap's
    # _heatmap_column_headers pattern -- the plot itself no longer needs top
    # margin reserved for its own label annotations.
    margin = dict(t=0, r=26, b=6, l=50) if compact else dict(t=0, r=30, b=8, l=60)
    x_axis_range = [stage_positions[0] - left_label_room, stage_positions[-1] + right_label_room]
    tone_label_x = x_axis_range[0] + (0.05 if compact else 0.06)
    band_x0 = tone_label_x + (0.18 if compact else 0.22)
    fig = go.Figure()

    tone_centers = {
        tone: (_RAG_FLOW_BAND_RANGES[tone][0] + _RAG_FLOW_BAND_RANGES[tone][1]) / 2
        for tone in _RAG_FLOW_TONE_ORDER
    }
    # Loss's "tones" are its Performance RAG repeated across all four slots
    # (see _rag_flow_models) purely so it still counts toward the Final RAG
    # buckets elsewhere on the page -- it has no real review/mitigation
    # pipeline, so the chart itself only plots it at stage 0 (Performance
    # RAG) and draws no transition lines for it at all.
    stage_counts = {
        stage_index: Counter(
            row["tones"][stage_index]
            for row in selected_rows
            if isinstance(row.get("tones"), list) and len(row["tones"]) == len(_RAG_FLOW_STAGES)
            and (stage_index == 0 or row.get("Model Group") != "Loss")
        )
        for stage_index in range(len(_RAG_FLOW_STAGES))
    }
    transition_counts = {
        stage_index: Counter(
            (row["tones"][stage_index], row["tones"][stage_index + 1])
            for row in selected_rows
            if isinstance(row.get("tones"), list) and len(row["tones"]) == len(_RAG_FLOW_STAGES)
            and row.get("Model Group") != "Loss"
        )
        for stage_index in range(len(_RAG_FLOW_STAGES) - 1)
    }

    for stage_index, transitions in transition_counts.items():
        x0 = stage_positions[stage_index]
        x1 = stage_positions[stage_index + 1]
        dx = x1 - x0
        for (source_tone, target_tone), count in transitions.items():
            source_y = tone_centers[source_tone]
            target_y = tone_centers[target_tone]
            fig.add_trace(go.Scatter(
                x=[x0, x0 + dx * 0.28, x0 + dx * 0.72, x1],
                y=[source_y, source_y, target_y, target_y],
                mode="lines",
                line=dict(
                    color=link_colors[source_tone],
                    width=min(14, 1.8 + (count ** 0.5) * (2.3 if compact else 2.6)),
                    shape="spline",
                    smoothing=1.1,
                ),
                customdata=[
                    [
                        "rag-transition",
                        _RAG_FLOW_STAGES[stage_index][1],
                        _RAG_FLOW_STAGES[stage_index + 1][1],
                        source_tone,
                        target_tone,
                        count,
                    ]
                ] * 4,
                hovertemplate=(
                    f"%{{customdata[5]}} {entity_label}(s)<br>%{{customdata[1]}}: %{{customdata[3]}}"
                    "<br>%{customdata[2]}: %{customdata[4]}<extra></extra>"
                ),
                showlegend=False,
            ))

    for stage_index, (_, stage_label) in enumerate(_RAG_FLOW_STAGES):
        tones = [tone for tone in _RAG_FLOW_TONE_ORDER if stage_counts[stage_index].get(tone, 0)]
        counts = [stage_counts[stage_index][tone] for tone in tones]
        if not tones:
            continue
        selected_stage = int(selection.get("stage_index", -1)) if selection else -1
        selected_tone = str(selection.get("tone", "") or "") if selection else ""
        fig.add_trace(go.Scatter(
            x=[stage_positions[stage_index]] * len(tones),
            y=[tone_centers[tone] for tone in tones],
            mode="markers+text",
            text=[str(count) for count in counts],
            textposition="middle center",
            textfont=dict(size=11 if compact else 13, color="#ffffff", family="Arial Black, Arial, sans-serif"),
            marker=dict(
                size=[min(58, 32 + (count ** 0.5) * 5) for count in counts],
                color=[marker_colors[tone] for tone in tones],
                line=dict(
                    color=[
                        palette["selected_outline"]
                        if stage_index == selected_stage and tone == selected_tone
                        else palette["node_outline"]
                        for tone in tones
                    ],
                    width=[
                        4 if stage_index == selected_stage and tone == selected_tone else 1.5
                        for tone in tones
                    ],
                ),
            ),
            customdata=[
                ["rag-bucket", stage_index, tone, count, stage_label]
                for tone, count in zip(tones, counts)
            ],
            hovertemplate=(
                f"%{{customdata[4]}}<br>%{{customdata[2]}}: %{{customdata[3]}} {entity_label}(s)"
                "<br><b>Click to explore</b><extra></extra>"
            ),
            showlegend=False,
        ))

    active_entity = str(selection.get("entity", "") or "") if selection else ""
    active_row = next(
        (row for row in selected_rows if str(row.get("Entity Label", "")) == active_entity),
        None,
    )
    selected_entity_annotations: list[dict[str, object]] = []
    if active_row is not None:
        tones = active_row["tones"]
        is_loss_row = active_row.get("Model Group") == "Loss"
        y_positions = [
            tone_centers[tone] + (0.032 if stage_index % 2 == 0 else -0.032)
            for stage_index, tone in enumerate(tones)
        ]
        # Loss has no real review/mitigation transitions to draw (see the
        # stage_counts/transition_counts note above) -- its highlighted path
        # is a single point at stage 0, not a line across all four stages.
        marker_stage_indices = [0] if is_loss_row else list(range(len(_RAG_FLOW_STAGES)))
        for stage_index in [] if is_loss_row else range(len(_RAG_FLOW_STAGES) - 1):
            x0 = stage_positions[stage_index]
            x1 = stage_positions[stage_index + 1]
            dx = x1 - x0
            x_values = [x0, x0 + dx * 0.28, x0 + dx * 0.72, x1]
            y_values = [y_positions[stage_index], y_positions[stage_index], y_positions[stage_index + 1], y_positions[stage_index + 1]]
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines",
                line=dict(color=marker_colors[tones[stage_index]], width=5.5 if compact else 6.5, shape="spline", smoothing=1.1),
                customdata=[
                    [
                        active_entity,
                        _RAG_FLOW_STAGES[stage_index][1],
                        _RAG_FLOW_STAGES[stage_index + 1][1],
                        tones[stage_index],
                        tones[stage_index + 1],
                    ]
                ] * 4,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>%{customdata[1]}: %{customdata[3]}"
                    "<br>%{customdata[2]}: %{customdata[4]}<extra></extra>"
                ),
                showlegend=False,
            ))

        wrapped_entity = _wrap_rag_flow_label(active_entity, 15 if compact else 20)
        annotation_stages = (
            ((0, "right", -20, "right"),)
            if is_loss_row
            else ((0, "right", -20, "right"), (len(_RAG_FLOW_STAGES) - 1, "left", 13, "left"))
        )
        selected_entity_annotations = [
            dict(
                x=stage_positions[stage_index],
                y=y_positions[stage_index],
                xref="x",
                yref="y",
                text=f"<b>{wrapped_entity}</b>",
                showarrow=False,
                xanchor=xanchor,
                yanchor="middle",
                xshift=xshift,
                align=align,
                font=dict(size=11 if compact else 12, color=text_color, family="Arial, sans-serif"),
            )
            for stage_index, xanchor, xshift, align in annotation_stages
        ]
        fig.add_trace(go.Scatter(
            x=[stage_positions[index] for index in marker_stage_indices],
            y=[y_positions[index] for index in marker_stage_indices],
            mode="markers",
            marker=dict(
                size=17 if compact else 19,
                color=[marker_colors[tones[index]] for index in marker_stage_indices],
                line=dict(width=0),
            ),
            customdata=[
                ["rag-entity", active_entity, _RAG_FLOW_STAGES[index][1], tones[index]]
                for index in marker_stage_indices
            ],
            hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[2]}: %{customdata[3]}<extra></extra>",
            showlegend=False,
        ))

    # Bottom caption: "all" lists everything (no bucket focus); a valid bucket
    # names the focused stage/tone; anything else (no selection) shows nothing.
    if selection and selection.get("all"):
        focus_caption = f"Showing all {len(selected_rows)} {entity_label}(s)"
    elif selection and int(selection.get("stage_index", -1)) in range(len(_RAG_FLOW_STAGES)) \
            and str(selection.get("tone", "")) in _RAG_FLOW_VALID_TONES:
        focus_caption = (
            f"Focused view · {len(selected_rows)} {entity_label}(s) from "
            f"{_RAG_FLOW_STAGES[int(selection['stage_index'])][1]} · {selection['tone']}"
        )
    else:
        focus_caption = ""

    fig.update_layout(
        height=height,
        margin=margin,
        font=dict(size=12, color=text_color),
        annotations=[
            dict(
                x=tone_label_x,
                y=(_RAG_FLOW_BAND_RANGES[tone][0] + _RAG_FLOW_BAND_RANGES[tone][1]) / 2,
                xref="x",
                yref="y",
                text=tone,
                showarrow=False,
                xanchor="left",
                font=dict(size=tone_font_size, color=label_colors[tone], family="Arial Black, Arial, sans-serif"),
            )
            for tone in ("Green", "Amber", "Red")
        ] + selected_entity_annotations + (
            [
                dict(
                    x=(stage_positions[0] + stage_positions[-1]) / 2,
                    y=0.015,
                    xref="x",
                    yref="paper",
                    text=focus_caption,
                    showarrow=False,
                    font=dict(size=10 if compact else 11, color=palette["focus_text"]),
                )
            ]
            if focus_caption
            else []
        ),
        shapes=[
            dict(
                type="rect",
                xref="x",
                yref="y",
                x0=band_x0,
                x1=stage_positions[-1] + 0.34,
                y0=_RAG_FLOW_BAND_RANGES[tone][0],
                y1=_RAG_FLOW_BAND_RANGES[tone][1],
                fillcolor=band_colors[tone],
                line=dict(width=0),
                layer="below",
            )
            for tone in ("Green", "Amber", "Red")
        ] + [
            dict(
                type="line",
                xref="x",
                yref="y",
                x0=stage_positions[index],
                x1=stage_positions[index],
                y0=0.03,
                y1=0.90,
                line=dict(color=palette["divider"], width=1),
                layer="below",
            )
            for index in range(len(_RAG_FLOW_STAGES))
        ],
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        clickmode="event+select",
        uirevision="rag-flow",
        xaxis=dict(
            range=x_axis_range,
            visible=False,
            fixedrange=True,
        ),
        yaxis=dict(range=[0.0, 0.905], visible=False, fixedrange=True),
    )
    _apply_transparent_background(fig)
    return fig


def _rag_flow_column_flex_weights(compact: bool) -> tuple[float, list[float], float]:
    """Flex weights (left spacer, one per stage, right spacer) so an HTML
    header row lines up with this chart's own stage_positions/label-room
    layout above, without hard-coding the current coordinates twice."""
    stage_positions = [0.24, 1.12, 2.0, 2.88] if compact else [0.18, 1.08, 1.98, 2.88]
    left_label_room = 0.66 if compact else 0.72
    right_label_room = 0.42 if compact else 0.48
    gaps = [stage_positions[index + 1] - stage_positions[index] for index in range(len(stage_positions) - 1)]
    column_widths = [
        (gaps[index - 1] if index > 0 else gaps[0]) / 2 + (gaps[index] if index < len(gaps) else gaps[-1]) / 2
        for index in range(len(stage_positions))
    ]
    spacer_left = max(0.0, left_label_room - column_widths[0] / 2)
    spacer_right = max(0.0, right_label_room - column_widths[-1] / 2)
    return spacer_left, column_widths, spacer_right


def _rag_flow_column_headers(compact: bool = False) -> html.Div:
    """HTML column headers for the RAG Migration Journey Sankey chart, styled
    and behaved identically to the Model RAG Heatmap's own column headers
    (``_heatmap_column_headers``): real, keyboard-focusable cells whose full
    definitions appear on hover/focus via CSS, positioned above the chart so
    its own xaxis no longer needs to render stage labels itself. Flex weights
    are derived from the chart's stage_positions so the cells line up with
    the Sankey columns underneath."""
    spacer_left, column_widths, spacer_right = _rag_flow_column_flex_weights(compact)
    cells = [
        html.Div(
            className="overview-heatmap-column-header-cell",
            tabIndex=0,
            style={"flex": column_widths[index]},
            children=[
                html.Span(stage_label, className="overview-heatmap-column-header-title"),
                html.Div(
                    className="overview-heatmap-column-tooltip",
                    children=[
                        html.Strong(stage_label),
                        html.Span(_RAG_FLOW_STAGE_DEFINITIONS[index]),
                    ],
                ),
            ],
        )
        for index, (_, stage_label) in enumerate(_RAG_FLOW_STAGES)
    ]
    # Horizontal padding mirrors the Sankey figure's own left/right margin
    # (see the `margin` dict in _rag_flow_sankey_figure) so the flex-based
    # spacer/column widths -- computed in data-coordinate space -- line up
    # with the chart's actual plot area in pixel space underneath.
    padding = "0 26px 0 50px" if compact else "0 30px 0 60px"
    return html.Div(
        className="overview-rag-flow-column-headers",
        style={"padding": padding},
        children=(
            [html.Div(className="overview-rag-flow-column-spacer", style={"flex": spacer_left})]
            + cells
            + [html.Div(className="overview-rag-flow-column-spacer", style={"flex": spacer_right})]
        ),
    )


def _rag_heatmap_figure(rows: list[dict], theme: str, columns: list[str] = RAG_COLUMNS) -> go.Figure:
    height = heatmap_chart_height(rows)
    if not rows:
        return _empty_figure("No models are in scope for the selected filters.", height=height, theme=theme)

    y_labels = [f"{row['Model Group']} · {row['Model']}" for row in rows]
    x_labels = [_heatmap_display_label(column) for column in columns]

    # N/A gets its own gray level (0) rather than sharing Amber's color (2) --
    # "no data" and "tested, found Amber" should never look the same.
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    z_values, text_values, customdata = [], [], []
    for row in rows:
        z_row, text_row, custom_row = [], [], []
        for column in columns:
            rag = row.get(column, "N/A")
            # RAG Assignment columns rely on color alone -- no metric is
            # computed for them, and a bare RAG word ("Amber") next to
            # Post Subjective Review's metric values would look inconsistent.
            # Post Subjective Review columns show their headline metric
            # instead of repeating the RAG word the color already conveys.
            is_metric_column = column in POST_SUBJECTIVE_COLUMNS
            metric = row.get(column.replace(" RAG", " Metric"), "—") if is_metric_column else ""
            has_metric = is_metric_column and metric != "—"
            z_row.append(heatmap_z.get(rag, 0))
            text_row.append(_wrap_metric_text(metric) if has_metric else "")
            metric_hover = f"<br>Metric: {metric}" if has_metric else ""
            # MEV Range is the one column whose result depends on which
            # Scenario was in effect (see augment_rows_with_post_subjective) --
            # surfaced here so hovering it shows which scenario produced the
            # RAG/metric shown, instead of leaving that silently invisible.
            scenario_hover = f"<br>Scenario: {row.get('MEV Range Scenario')}" if column == "MEV Range RAG" and row.get("MEV Range Scenario") else ""
            custom_row.append([row["Model Group"], row["Model"], _heatmap_display_label(column), display_rag(rag), row.get("Monitoring Period", ""), metric_hover, scenario_hover])
        z_values.append(z_row)
        text_values.append(text_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=x_labels,
        y=y_labels,
        z=z_values,
        text=text_values,
        texttemplate="%{text}",
        textfont=dict(size=10, color="#0f172a"),
        customdata=customdata,
        zmin=0,
        zmax=3,
        xgap=5,
        ygap=5,
        colorscale=[
            [0.00, "rgba(148,163,184,0.45)"], [0.25, "rgba(148,163,184,0.45)"],
            [0.25, "rgba(22,163,74,0.55)"], [0.50, "rgba(22,163,74,0.55)"],
            [0.50, "rgba(245,158,11,0.55)"], [0.75, "rgba(245,158,11,0.55)"],
            [0.75, "rgba(220,38,38,0.65)"], [1.00, "rgba(220,38,38,0.65)"],
        ],
        # Plotly's built-in colorbar silently reserves extra width beyond the
        # margins below, which the HTML column headers above the chart can't
        # predict -- causing them to drift out of alignment with the actual
        # columns. Disabled here in favor of the static _rag_swatch_legend()
        # placed alongside the chart, so the plot's rendered width (and thus
        # every column's position) is fully determined by ``margin`` alone.
        showscale=False,
        hovertemplate=(
            "%{customdata[0]} — %{customdata[1]}<br>%{customdata[2]}: %{customdata[3]}"
            "%{customdata[5]}%{customdata[6]}"
            "<br>As of %{customdata[4]}<extra></extra>"
        ),
    ))
    # Emphasize Overall RAG as the roll-up verdict of the RAG Assignment
    # tests without separating it into a different panel.
    if "Overall RAG" in columns:
        overall_idx = columns.index("Overall RAG")
        fig.add_shape(
            type="rect",
            xref="x",
            x0=overall_idx - 0.5,
            x1=overall_idx + 0.5,
            yref="paper",
            y0=0,
            y1=1,
            fillcolor="rgba(37,99,235,0.05)",
            line=dict(width=0),
            layer="below",
        )
        if overall_idx > 0:
            fig.add_shape(
                type="line",
                xref="x",
                x0=overall_idx - 0.5,
                x1=overall_idx - 0.5,
                yref="paper",
                y0=0,
                y1=1,
                line=dict(color="rgba(37,99,235,0.45)", width=2),
            )
    # Visually separate the RAG Assignment columns from the Post Subjective
    # Review columns, and those from the trailing Final RAG column, within
    # the single combined heatmap.
    for boundary in (len(RAG_ASSIGNMENT_COLUMNS) - 0.5, len(RAG_ASSIGNMENT_COLUMNS) + len(POST_SUBJECTIVE_COLUMNS) - 0.5):
        if boundary < len(columns) - 1:
            fig.add_shape(type="line", xref="x", x0=boundary, x1=boundary, yref="paper", y0=0, y1=1, line=dict(color="rgba(100,116,139,0.55)", width=2, dash="dot"))
    fig.update_layout(
        height=height,
        margin=dict(t=6, r=20, b=40, l=190),
        # Column labels are rendered by _heatmap_column_headers() above the
        # chart, with the definitions exposed on hover/focus, so the plot's
        # own top axis stays hidden to avoid duplicating the labels.
        xaxis=dict(side="top", showticklabels=False, showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(tickfont=dict(size=12), autorange="reversed", automargin=True, fixedrange=True),
        hoverlabel=dict(bgcolor="#0f172a", bordercolor="rgba(15,23,42,0.10)", font=dict(color="#f8fafc", size=11)),
    )
    _apply_transparent_background(fig)
    return fig


def _rag_trend_heatmap_height(model_keys: list[tuple[str, str]]) -> int:
    return max(200, 70 + 48 * len(model_keys))


def _rag_trend_heatmap_figure(rows: list[dict], rag_column: str, visible_periods: list[str] | None, theme: str) -> go.Figure:
    """Every model's RAG for ``rag_column``, one row per model and one column
    per quarter -- same read as the 1.2 heatmap, just with time on the x-axis
    instead of test dimensions."""
    all_periods = available_periods(rows)
    periods = [p for p in all_periods if visible_periods is None or p in set(visible_periods)]
    period_set = set(periods)
    # A model whose own history starts after (or ends before) the visible
    # period window -- e.g. capping to an early Monitoring Point when this
    # model's earliest quarter is later -- would otherwise still show up as a
    # row with every cell "N/A". That's pure clutter, not information, so
    # only keep models with at least one row inside the visible window.
    models_in_window = {(row["Model Group"], row["Model"]) for row in rows if row["Monitoring Period"] in period_set}
    model_keys = sorted(
        models_in_window,
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )
    height = _rag_trend_heatmap_height(model_keys)
    if not model_keys or not periods:
        return _empty_figure("No RAG trend data is available for the selected filters.", height=height, theme=theme)

    by_key_period = {(row["Model Group"], row["Model"], row["Monitoring Period"]): row.get(rag_column, "N/A") for row in rows}
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    y_labels = [f"{group} · {model}" for group, model in model_keys]
    z_values, customdata = [], []
    for group, model in model_keys:
        z_row, custom_row = [], []
        for period in periods:
            rag = by_key_period.get((group, model, period), "N/A")
            z_row.append(heatmap_z.get(rag, 0))
            custom_row.append([group, model, display_rag(rag), period])
        z_values.append(z_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=periods,
        y=y_labels,
        z=z_values,
        customdata=customdata,
        zmin=0,
        zmax=3,
        xgap=3,
        ygap=5,
        colorscale=[
            [0.00, "rgba(148,163,184,0.45)"], [0.25, "rgba(148,163,184,0.45)"],
            [0.25, "rgba(22,163,74,0.55)"], [0.50, "rgba(22,163,74,0.55)"],
            [0.50, "rgba(245,158,11,0.55)"], [0.75, "rgba(245,158,11,0.55)"],
            [0.75, "rgba(220,38,38,0.65)"], [1.00, "rgba(220,38,38,0.65)"],
        ],
        showscale=False,
        hovertemplate="%{customdata[0]} — %{customdata[1]}<br>%{customdata[3]}: %{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(t=10, r=20, b=50, l=190),
        xaxis=build_pd_time_series_xaxis(periods, {"gridcolor": "#e5e7eb"}, density="tight"),
        yaxis=dict(tickfont=dict(size=12), autorange="reversed"),
    )
    _apply_transparent_background(fig)
    return fig


def _segment_heatmap_figure(rows: list[dict], theme: str, columns: list[str] = RAG_COLUMNS) -> go.Figure:
    """Segments-chapter equivalent of ``_rag_heatmap_figure``: one row per
    (Model Group, Model, Segment) instead of per model -- more than one model
    within a group can cover the same segment, so the model disambiguates
    which model's data a row shows. Keeps the same margins as the model
    heatmap (rather than shrinking the left margin for shorter labels) so
    both chapters share the same ``_heatmap_panel``/column-header CSS."""
    height = heatmap_chart_height(rows)
    if not rows:
        return _empty_figure("No segments are in scope for the selected filters.", height=height, theme=theme)

    y_labels = [
        f"{row['Model Group']} · {row['Model']} · {row['Segment']}" if row.get("Model") else f"{row['Model Group']} · {row['Segment']}"
        for row in rows
    ]
    x_labels = [_heatmap_display_label(column) for column in columns]
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    z_values, text_values, customdata = [], [], []
    for row in rows:
        z_row, text_row, custom_row = [], [], []
        for column in columns:
            rag = row.get(column, "N/A")
            is_metric_column = column in POST_SUBJECTIVE_COLUMNS
            metric = row.get(column.replace(" RAG", " Metric"), "—") if is_metric_column else ""
            has_metric = is_metric_column and metric != "—"
            z_row.append(heatmap_z.get(rag, 0))
            text_row.append(_wrap_metric_text(metric) if has_metric else "")
            metric_hover = f"<br>Metric: {metric}" if has_metric else ""
            # See the matching comment in _rag_heatmap_figure.
            scenario_hover = f"<br>Scenario: {row.get('MEV Range Scenario')}" if column == "MEV Range RAG" and row.get("MEV Range Scenario") else ""
            custom_row.append([row["Model Group"], row["Segment"], _heatmap_display_label(column), display_rag(rag), row.get("Monitoring Period", ""), metric_hover, row.get("Model", ""), scenario_hover])
        z_values.append(z_row)
        text_values.append(text_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=x_labels,
        y=y_labels,
        z=z_values,
        text=text_values,
        texttemplate="%{text}",
        textfont=dict(size=10, color="#0f172a"),
        customdata=customdata,
        zmin=0,
        zmax=3,
        xgap=5,
        ygap=5,
        colorscale=[
            [0.00, "rgba(148,163,184,0.45)"], [0.25, "rgba(148,163,184,0.45)"],
            [0.25, "rgba(22,163,74,0.55)"], [0.50, "rgba(22,163,74,0.55)"],
            [0.50, "rgba(245,158,11,0.55)"], [0.75, "rgba(245,158,11,0.55)"],
            [0.75, "rgba(220,38,38,0.65)"], [1.00, "rgba(220,38,38,0.65)"],
        ],
        showscale=False,
        hovertemplate=(
            "%{customdata[0]} — %{customdata[6]} — %{customdata[1]}<br>%{customdata[2]}: %{customdata[3]}"
            "%{customdata[5]}%{customdata[7]}"
            "<br>As of %{customdata[4]}<extra></extra>"
        ),
    ))
    for boundary in (len(RAG_ASSIGNMENT_COLUMNS) - 0.5, len(RAG_ASSIGNMENT_COLUMNS) + len(POST_SUBJECTIVE_COLUMNS) - 0.5):
        if boundary < len(columns) - 1:
            fig.add_shape(type="line", xref="x", x0=boundary, x1=boundary, yref="paper", y0=0, y1=1, line=dict(color="rgba(100,116,139,0.55)", width=2, dash="dot"))
    fig.update_layout(
        height=height,
        margin=dict(t=6, r=20, b=40, l=190),
        xaxis=dict(side="top", showticklabels=False),
        yaxis=dict(tickfont=dict(size=12), autorange="reversed"),
    )
    _apply_transparent_background(fig)
    return fig


def _segment_trend_heatmap_height(segment_keys: list[str]) -> int:
    return max(200, 70 + 48 * len(segment_keys))


def _segment_trend_heatmap_figure(rows: list[dict], rag_column: str, visible_periods: list[str] | None, theme: str) -> go.Figure:
    """Segments-chapter equivalent of ``_rag_trend_heatmap_figure``.

    Keyed by (Model Group, Model, Segment) rather than just (Model Group,
    Segment) -- more than one model within a group can cover the same
    segment, so the model name disambiguates which model's data a row shows.
    """
    all_periods = available_periods(rows)
    periods = [p for p in all_periods if visible_periods is None or p in set(visible_periods)]
    period_set = set(periods)
    # See the matching comment in _rag_trend_heatmap_figure: drop rows with no
    # data at all inside the visible period window rather than showing an
    # all-"N/A" row.
    segments_in_window = {
        (row["Model Group"], row.get("Model", ""), row["Segment"])
        for row in rows
        if row["Monitoring Period"] in period_set
    }
    segment_keys = sorted(
        segments_in_window,
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1], key[2]),
    )
    height = _segment_trend_heatmap_height(segment_keys)
    if not segment_keys or not periods:
        return _empty_figure("No RAG trend data is available for the selected filters.", height=height, theme=theme)

    by_key_period = {
        (row["Model Group"], row.get("Model", ""), row["Segment"], row["Monitoring Period"]): row.get(rag_column, "N/A")
        for row in rows
    }
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    y_labels = [f"{group} · {model} · {segment}" if model else f"{group} · {segment}" for group, model, segment in segment_keys]
    z_values, customdata = [], []
    for group, model, segment in segment_keys:
        z_row, custom_row = [], []
        for period in periods:
            rag = by_key_period.get((group, model, segment, period), "N/A")
            z_row.append(heatmap_z.get(rag, 0))
            custom_row.append([group, segment, display_rag(rag), period, model])
        z_values.append(z_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=periods,
        y=y_labels,
        z=z_values,
        customdata=customdata,
        zmin=0,
        zmax=3,
        xgap=3,
        ygap=5,
        colorscale=[
            [0.00, "rgba(148,163,184,0.45)"], [0.25, "rgba(148,163,184,0.45)"],
            [0.25, "rgba(22,163,74,0.55)"], [0.50, "rgba(22,163,74,0.55)"],
            [0.50, "rgba(245,158,11,0.55)"], [0.75, "rgba(245,158,11,0.55)"],
            [0.75, "rgba(220,38,38,0.65)"], [1.00, "rgba(220,38,38,0.65)"],
        ],
        showscale=False,
        hovertemplate="%{customdata[0]} — %{customdata[4]} — %{customdata[1]}<br>%{customdata[3]}: %{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(t=10, r=20, b=50, l=190),
        xaxis=build_pd_time_series_xaxis(periods, {"gridcolor": "#e5e7eb"}, density="tight"),
        yaxis=dict(tickfont=dict(size=12), autorange="reversed"),
    )
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _build_summary_section(
    current_rows: list[dict], findings: list[dict], monitoring_point: str, theme: str,
    chapter1_exclusions: list[dict] | None = None,
) -> html.Section:
    summary = overview_summary(current_rows)

    return html.Section(
        id="overview-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Model Overview",
                "RAG Assignment Overview",
                "",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            _final_post_mitigation_distribution_card(current_rows, exclusions=chapter1_exclusions),
            _rag_flow_summary_card(current_rows, theme),
        ],
    )


def _build_segment_summary_section(current_rows: list[dict], findings: list[dict], monitoring_point: str, theme: str) -> html.Section:
    """Segments-chapter equivalent of ``_build_summary_section``."""
    summary = segment_overview_summary(current_rows)

    return html.Section(
        id="overview-segment-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 Segment Overview",
                "Segment RAG Assignment Overview",
                "",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            _final_post_mitigation_distribution_card(current_rows, entity_kind="segment"),
            _rag_flow_summary_card(current_rows, theme, entity_kind="segment"),
        ],
    )


def _heatmap_group_headers() -> html.Div:
    """A thin banner spanning the assignment, post-subjective, and final
    mitigation-stage columns so the combined heatmap still reads in chapter
    order."""
    return html.Div(
        className="overview-heatmap-group-headers",
        children=[
            html.Div(
                "1. RAG Assignment",
                className="overview-heatmap-group-header-cell overview-heatmap-group-header-assignment",
                style={"flex": len(RAG_ASSIGNMENT_COLUMNS)},
            ),
            html.Div("2. Post Subjective Review", className="overview-heatmap-group-header-cell overview-heatmap-group-header-review", style={"flex": len(POST_SUBJECTIVE_COLUMNS)}),
            html.Div("3. Final RAG", className="overview-heatmap-group-header-cell overview-heatmap-group-header-final", style={"flex": len(HEATMAP_FINAL_COLUMNS)}),
        ],
    )


def _heatmap_display_label(column: str) -> str:
    if column == "Overall RAG":
        return "Performance RAG"
    if column == FINAL_RAG_COLUMN:
        return "Final RAG"
    if column in HEATMAP_FINAL_COLUMNS:
        return column
    return column.replace(" RAG", "")


def _heatmap_column_headers(columns: list[str]) -> html.Div:
    """Column labels whose full definitions appear when hovering the header
    boxes themselves, keeping the heatmap tidy while preserving context."""
    def _tooltip(column: str) -> html.Div:
        return html.Div(
            className="overview-heatmap-column-tooltip",
            children=[
                html.Strong(_heatmap_display_label(column)),
                html.Span(RAG_COLUMN_DESCRIPTIONS[column]),
            ],
        )

    def _cell(column: str) -> html.Div:
        extra_classes = []
        if column in {
            "Calibration RAG",
            "Discrimination RAG",
            "Overall RAG",
            "Transition Matrix RAG",
            "PSI RAG",
            "Scenario Ranking RAG",
            "Sensitivity Analysis RAG",
        }:
            extra_classes.extend(["overview-heatmap-column-header-operator", "overview-heatmap-column-header-operator-plus"])
        elif column in {"Balance Sheet Calibration RAG", "MEV Range RAG"}:
            extra_classes.extend(["overview-heatmap-column-header-operator", "overview-heatmap-column-header-operator-equals"])
        elif column in {"Post Subjective Review RAG", "Pre Mitigation RAG"}:
            extra_classes.extend(["overview-heatmap-column-header-operator", "overview-heatmap-column-header-operator-arrow"])
        if column == "Overall RAG":
            return html.Div(
                className=" ".join([
                    "overview-heatmap-column-header-cell",
                    "overview-heatmap-column-header-overall",
                    *extra_classes,
                ]),
                tabIndex=0,
                children=[
                    html.Span("Performance RAG", className="overview-heatmap-column-header-title"),
                    _tooltip(column),
                ],
            )
        if column in HEATMAP_FINAL_COLUMNS:
            return html.Div(
                className=" ".join([
                    "overview-heatmap-column-header-cell",
                    "overview-heatmap-column-header-final",
                    *extra_classes,
                ]).strip(),
                tabIndex=0,
                children=[
                    html.Span(_heatmap_display_label(column), className="overview-heatmap-column-header-title"),
                    _tooltip(column),
                ],
            )
        return html.Div(
            className=" ".join(["overview-heatmap-column-header-cell", *extra_classes]).strip(),
            tabIndex=0,
            children=[
                html.Span(_heatmap_display_label(column), className="overview-heatmap-column-header-title"),
                _tooltip(column),
            ],
        )

    return html.Div(
        className="overview-heatmap-column-headers",
        children=[_cell(column) for column in columns],
    )


def _rag_swatch_legend(horizontal: bool = False) -> html.Div:
    """Static RAG legend replacing Plotly's built-in colorbar (see the
    ``showscale=False`` note in ``_rag_heatmap_figure``). Defaults to a
    fixed-width sidebar beside the chart (used by the RAG Trend row); pass
    ``horizontal=True`` for the RAG Heatmap panel, where the legend renders
    as a strip below the chart instead, freeing up the full card width for
    the plot's row-label margin (long model names need the room)."""
    return html.Div(
        className="overview-heatmap-swatch-legend overview-heatmap-swatch-legend-horizontal" if horizontal else "overview-heatmap-swatch-legend",
        children=[
            html.Div("RAG", className="overview-heatmap-swatch-legend-title"),
            *[
                html.Div(
                    className="overview-heatmap-swatch-legend-item",
                    children=[html.Span(className=f"overview-heatmap-swatch overview-heatmap-swatch-{tone}"), html.Span(label)],
                )
                for tone, label in (("red", "Red"), ("amber", "Amber"), ("green", "Green"), ("na", "N/A"))
            ],
        ],
    )


def _heatmap_panel(rows: list[dict], columns: list[str], theme: str, title: str, subtitle: str, figure_fn=_rag_heatmap_figure) -> html.Div:
    return html.Div(
        className="section-card",
        children=[
            build_chart_header(title, subtitle),
            html.Div(
                className="overview-heatmap-plot-column",
                children=[
                    _heatmap_group_headers(),
                    _heatmap_column_headers(columns),
                    dcc.Graph(
                        figure=figure_fn(rows, theme, columns),
                        config=_GRAPH_CONFIG,
                        style={"height": f"{heatmap_chart_height(rows)}px"},
                    ),
                ],
            ),
            _rag_swatch_legend(horizontal=True),
        ],
    )


def _build_heatmap_section(current_rows: list[dict], theme: str, monitoring_point: str = "All") -> html.Section:
    rows = heatmap_rows(current_rows)
    period_label = monitoring_point if monitoring_point and monitoring_point != "All" else "each model's latest period"
    return html.Section(
        id="overview-heatmap",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 Model RAG Heatmap",
                f"Cross-Model RAG Comparison — {period_label}",
                "Every monitored model's RAG Assignment and Post Subjective Review tests side by side, mirroring "
                "the chapter structure of each individual Performance tab.",
                "Green",
                {"show_rag": False},
            ),
            _heatmap_panel(
                rows, HEATMAP_COLUMNS, theme,
                "Model RAG Heatmap",
                "Color shows each test's RAG — hover a column header or cell for detail.",
            ),
        ],
    )


def _build_segment_heatmap_section(current_rows: list[dict], theme: str, monitoring_point: str = "All") -> html.Section:
    rows = segment_heatmap_rows(current_rows)
    period_label = monitoring_point if monitoring_point and monitoring_point != "All" else "each segment's latest period"
    return html.Section(
        id="overview-segment-heatmap",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.2 Segment RAG Heatmap",
                f"Cross-Segment RAG Comparison — {period_label}",
                "Every monitored segment's RAG Assignment and Post Subjective Review tests side by side, one row "
                "per model group per model per segment (more than one model can cover the same segment name, so "
                "each row is scoped to a single model).",
                "Green",
                {"show_rag": False},
            ),
            _heatmap_panel(
                rows, HEATMAP_COLUMNS, theme,
                "Segment RAG Heatmap",
                "Color shows each test's RAG — hover a column header or cell for detail.",
                figure_fn=_segment_heatmap_figure,
            ),
        ],
    )


def build_trend_figure(rows: list[dict], rag_trend_metric: str, range_store: dict | None, theme: str, monitoring_point: str = "All") -> go.Figure:
    """Build the portfolio RAG trend figure. Shared by the initial section render and the
    dimension/range-driven mini-callback that updates the chart without a full re-render."""
    rag_trend_metric = rag_trend_metric if rag_trend_metric in HEATMAP_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), all_periods)
    return _rag_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str, monitoring_point: str = "All") -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in HEATMAP_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), all_periods)
    model_keys = sorted(
        {(row["Model Group"], row["Model"]) for row in rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )

    return html.Section(
        id="overview-rag-trend",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.3 Model RAG Trend Analysis",
                "Period-over-Period RAG Movement",
                "Every model's RAG for the selected dimension, one row per model and one column per quarter.",
                "Green",
                {"show_rag": False},
            ),
            html.Div(
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Portfolio RAG Trend",
                        "Pick a RAG dimension to trend across every model.",
                        RAG_TREND_RANGE_KEY,
                        all_periods,
                        range_store.get(RAG_TREND_RANGE_KEY),
                        extra_controls=_build_filter(
                            "RAG Dimension",
                            shared_filters.build_single_select_dropdown(
                                value_id=RAG_TREND_METRIC_ID,
                                toggle_id=RAG_TREND_METRIC_TOGGLE_ID,
                                menu_id=RAG_TREND_METRIC_MENU_ID,
                                filter_key=RAG_TREND_METRIC_FILTER_KEY,
                                options=_rag_trend_dropdown_options(HEATMAP_COLUMNS),
                                value=rag_trend_metric,
                            ),
                        ),
                    ),
                    dcc.Graph(
                        id=RAG_TREND_CHART_ID,
                        figure=_rag_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme),
                        config=_GRAPH_CONFIG,
                        style={"height": f"{_rag_trend_heatmap_height(model_keys)}px"},
                    ),
                    _rag_swatch_legend(horizontal=True),
                ],
            ),
        ],
    )


def build_segment_trend_figure(rows: list[dict], rag_trend_metric: str, range_store: dict | None, theme: str, monitoring_point: str = "All") -> go.Figure:
    """Segments-chapter equivalent of ``build_trend_figure``."""
    rag_trend_metric = rag_trend_metric if rag_trend_metric in HEATMAP_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(SEGMENT_RAG_TREND_RANGE_KEY), all_periods)
    return _segment_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_segment_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str, monitoring_point: str = "All") -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in HEATMAP_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(SEGMENT_RAG_TREND_RANGE_KEY), all_periods)
    segment_keys = sorted({(row["Model Group"], row.get("Model", ""), row["Segment"]) for row in rows})

    return html.Section(
        id="overview-segment-rag-trend",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.3 Segment RAG Trend Analysis",
                "Period-over-Period RAG Movement",
                "Every segment's RAG for the selected dimension, one row per segment and one column per quarter.",
                "Green",
                {"show_rag": False},
            ),
            html.Div(
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Segment RAG Trend",
                        "Pick a RAG dimension to trend across every segment.",
                        SEGMENT_RAG_TREND_RANGE_KEY,
                        all_periods,
                        range_store.get(SEGMENT_RAG_TREND_RANGE_KEY),
                        extra_controls=_build_filter(
                            "RAG Dimension",
                            shared_filters.build_single_select_dropdown(
                                value_id=SEGMENT_RAG_TREND_METRIC_ID,
                                toggle_id=SEGMENT_RAG_TREND_METRIC_TOGGLE_ID,
                                menu_id=SEGMENT_RAG_TREND_METRIC_MENU_ID,
                                filter_key=SEGMENT_RAG_TREND_METRIC_FILTER_KEY,
                                options=_rag_trend_dropdown_options(HEATMAP_COLUMNS),
                                value=rag_trend_metric,
                            ),
                        ),
                    ),
                    dcc.Graph(
                        id=SEGMENT_RAG_TREND_CHART_ID,
                        figure=_segment_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme),
                        config=_GRAPH_CONFIG,
                        style={"height": f"{_segment_trend_heatmap_height(segment_keys)}px"},
                    ),
                    _rag_swatch_legend(horizontal=True),
                ],
            ),
        ],
    )


def _esc_posture(esc: dict, entity_noun: str) -> tuple[str, str]:
    """(posture title, tone) for the escalation board, derived from the tiers
    themselves so the headline can never disagree with the cards below it."""
    counts = esc["counts"]
    if esc["total"] == 0:
        return f"No {entity_noun}s in scope", "neutral"
    if counts["escalate"]:
        return "Escalation required", "red"
    if counts["watch"]:
        return "Review required", "amber"
    return "In tolerance", "green"


_ESC_TIER_LABELS = {"escalate": "require escalation", "watch": "on watch", "clear": "in tolerance"}
_ESC_TIER_TONES = {"escalate": "red", "watch": "amber", "clear": "green"}
_ESC_STAGE_KICKERS = {"Pre Mitigation": "Pre mitigation", "Post Mitigation": "Post mitigation"}
_ESC_RAG_RANK = {"N/A": -1, "Green": 0, "Amber": 1, "Red": 2}
# Short labels for the collapsed-row review-flow dots, so each dot names its
# stage without needing a hover. Keyed by the REVIEW_FLOW_STAGES field key.
_ESC_FLOW_SHORT_LABELS = {
    "post_subjective": "Post SR",
    "pre_mitigation": "Pre Mit",
    "post_mitigation": "Post Mit",
}


def _esc_tier_chip(tier: str, count: int) -> html.Span:
    return html.Span(
        [html.Strong(str(count)), html.Span(_ESC_TIER_LABELS[tier])],
        className=(
            f"overview-esc-tier-chip overview-esc-tier-chip-{_ESC_TIER_TONES[tier]}"
            + ("" if count else " overview-esc-tier-chip-zero")
        ),
    )


def _governance_driver_chip(driver: str, driver_rags: dict[str, str], label: str | None = None) -> html.Span:
    return html.Span(
        label or driver,
        className=f"overview-governance-driver-chip overview-governance-driver-chip-{pd_tone_class(driver_rags.get(driver, 'Red'))}",
    )


def _driver_display_label(metric: str, record: dict) -> str:
    """MEV Range's RAG depends on which Scenario it was computed under (see
    augment_rows_with_post_subjective) -- appended here so the driver chip/
    watch-row line names it instead of leaving that silently invisible."""
    if metric == "MEV Range RAG" and record.get("MEV Range Scenario"):
        return f"{metric} ({record['MEV Range Scenario']})"
    return metric


def _esc_review_flow_strip(record: dict) -> html.Div:
    """The entity's Post Subjective Review -> Pre Mitigation -> Post Mitigation
    verdicts as a mini pipeline -- the same lifecycle each tab's 3.1 Conclusion
    diagram shows, compressed to fit an escalation card."""
    children = []
    for index, (field, column, _label) in enumerate(REVIEW_FLOW_STAGES):
        rag = record["Review Flow"].get(field, "N/A")
        if index:
            children.append(html.Span("→", className="overview-esc-flow-arrow", **{"aria-hidden": "true"}))
        children.append(
            html.Div(
                className=f"overview-esc-flow-stage overview-esc-flow-stage-{pd_tone_class(rag)}",
                children=[
                    html.Span(column, className="overview-esc-flow-stage-label"),
                    html.Span([pd_rag_dot(rag), html.Strong(rag)], className="overview-esc-flow-stage-value"),
                ],
            )
        )
    aria = "Review flow: " + ", ".join(
        f"{column} {record['Review Flow'].get(field, 'N/A')}" for field, column, _label in REVIEW_FLOW_STAGES
    )
    return html.Div(children, className="overview-esc-flow", role="img", **{"aria-label": aria})


def _esc_next_step_row(selection: dict) -> html.Div:
    """One playbook stage's prescription: driving RAG, required action, and the
    governance flags/owner/due that matter -- the Overview's compressed version
    of the tab Conclusion's Required Actions card."""
    action = selection.get("action")
    stage = selection["stage"]
    rag = selection["rag"]
    kicker = _ESC_STAGE_KICKERS.get(stage, stage)
    heading = html.Div(
        className="overview-esc-step-heading",
        children=[
            html.Span(kicker, className="overview-esc-step-kicker"),
            html.Span([pd_rag_dot(rag), html.Strong(rag)], className="overview-esc-step-rag"),
        ],
    )

    if not action:
        return html.Div(
            className="overview-esc-step overview-esc-step-na",
            children=[
                heading,
                html.Div(
                    "No playbook action matches this stage yet — set its RAG in the tab's Conclusion section.",
                    className="overview-esc-step-action",
                ),
            ],
        )

    children = [heading]
    if selection.get("persistent_breach"):
        children.append(
            html.Div("Persistent breach — two consecutive Red quarters", className="overview-esc-step-breach")
        )
    # Labeled detail blocks matching the tab Conclusion's Required Actions card:
    # a description line, then Required action / Additional requirements /
    # Escalation-discussion, reusing that card's own CSS classes so the two
    # views read identically.
    if action.get("description"):
        children.append(html.Div(action["description"], className="pd-action-description"))
    children.append(
        html.Div(
            className="pd-action-detail pd-action-detail-primary",
            children=[html.Span("Required action"), html.P(action["required_action"])],
        )
    )
    if action.get("additional_requirements"):
        children.append(
            html.Div(
                className="pd-action-detail",
                children=[html.Span("Additional requirements"), html.P(action["additional_requirements"])],
            )
        )
    if action.get("escalation"):
        children.append(
            html.Div(
                className="pd-action-detail",
                children=[html.Span("Escalation / discussion"), html.P(action["escalation"])],
            )
        )

    flags = [
        label
        for key, label in (("sponsor_approval", "Sponsor approval"), ("deep_dive", "Deep dive"), ("redevelopment", "Redevelopment"))
        if str(action.get(key, "")).strip().lower() == "yes"
    ]
    footer = []
    if flags:
        footer.append(
            html.Span([html.Span(flag, className="overview-esc-step-flag") for flag in flags], className="overview-esc-step-flags")
        )
    meta = " · ".join(
        part for part in (
            f"Owner: {action['owner']}" if action.get("owner") else "",
            f"Due in: {action['due_in_report']}" if action.get("due_in_report") else "",
        ) if part
    )
    if meta:
        footer.append(html.Span(meta, className="overview-esc-step-meta"))
    if footer:
        children.append(html.Div(footer, className="overview-esc-step-footer"))
    return html.Div(children, className=f"overview-esc-step overview-esc-step-{pd_tone_class(rag)}")


def _esc_flow_summary_dots(record: dict) -> html.Span:
    """Compact review-flow readout for the collapsed summary row -- one labeled
    dot per stage (Post SR / Pre Mit / Post Mit), each naming its RAG type and
    carrying a full-name hover title, so the collapsed list shows each entity's
    governance verdicts at a glance without expanding it."""
    if not record["Has Review Flow"]:
        return html.Span("No review flow", className="overview-esc-row-flow-empty")
    items = []
    for field, column, _label in REVIEW_FLOW_STAGES:
        rag = record["Review Flow"].get(field, "N/A")
        items.append(
            html.Span(
                className="overview-esc-row-flow-item",
                title=f"{column}: {rag}",
                children=[
                    html.Span(_ESC_FLOW_SHORT_LABELS.get(field, field), className="overview-esc-row-flow-label"),
                    html.Span(pd_rag_dot(rag), className="overview-esc-row-flow-dot"),
                ],
            )
        )
    aria = "Review flow: " + ", ".join(
        f"{column} {record['Review Flow'].get(field, 'N/A')}" for field, column, _label in REVIEW_FLOW_STAGES
    )
    return html.Span(items, className="overview-esc-row-flow", role="img", **{"aria-label": aria})


def _esc_tab_href(record: dict, reporting_cycle: str, entity_key: str) -> str:
    """Deep-link to the entity's own Performance tab: the target tab reads
    these query params (see ``parse_deep_link_params``) to pre-populate its
    top filters and render this exact scope immediately, instead of landing
    on the getting-started prompt and requiring an extra "Apply filters" click."""
    params = {"cycle": reporting_cycle, "monitoring_point": record["Monitoring Period"]}
    if entity_key == "Segment":
        # A segment name can be shared across more than one model (see
        # escalation_next_steps' own (Model Group, Model, entity) grouping),
        # so the record's Model must come along too -- segment-only would
        # fall back to a pooled "home model" for the segment, which may not
        # be the specific model this card is actually about.
        params["segment"] = record["Entity"]
        params["model"] = record["Model"]
    else:
        params["model"] = record["Model"]
    # The scenario MEV Range was actually computed under for this entity (see
    # augment_rows_with_post_subjective) -- carried along so the target tab's
    # own Scenario filter (and thus its own MEV Range section) matches what
    # this card showed, instead of silently reverting to the tab's default.
    if record.get("MEV Range Scenario"):
        params["scenario"] = record["MEV Range Scenario"]
    return f"{record['Tab Path']}?{urlencode(params)}"


def _esc_row(record: dict, reporting_cycle: str, entity_key: str) -> html.Details:
    """One escalating entity as a native collapsible row: the summary shows the
    identity, severity, and a glanceable review-flow readout; expanding reveals
    the full review-flow pipeline, drivers, playbook next steps, the reviewer's
    sign-off, and a link to the source tab. Native ``<details>`` so no callback
    is needed and each row survives a full content re-render."""
    ribbon = "Persistent breach" if record["Persistent Breach"] else "Escalation required"
    row_class = "overview-esc-row" + (" overview-esc-row-breach" if record["Persistent Breach"] else "")

    summary = html.Summary(
        className="overview-esc-row-summary",
        children=[
            html.Span("▸", className="overview-esc-row-chevron", **{"aria-hidden": "true"}),
            html.Span(record["Model Group"], className="overview-esc-card-group"),
            html.Strong(record["Entity Label"], className="overview-esc-row-name"),
            html.Span(ribbon, className="overview-esc-row-ribbon"),
            _esc_flow_summary_dots(record),
            html.Span(record["Monitoring Period"], className="overview-esc-row-period"),
        ],
    )

    body_children = []
    if record["Has Review Flow"]:
        body_children.append(_esc_review_flow_strip(record))
    if record["Drivers"]:
        driver_rags = dict(record["Drivers"])
        body_children.append(
            html.Div(
                className="overview-esc-card-drivers",
                children=[
                    html.Span("Driven by", className="overview-esc-card-drivers-label"),
                    *[
                        _governance_driver_chip(metric, driver_rags, _driver_display_label(metric, record))
                        for metric, _rag in record["Drivers"]
                    ],
                ],
            )
        )
    if record["Selections"]:
        body_children.append(
            html.Div(
                className="overview-esc-card-steps",
                children=[_esc_next_step_row(selection) for selection in record["Selections"]],
            )
        )
    elif not record["Has Review Flow"]:
        body_children.append(
            html.Div(
                f"The {record['Model Group']} workstream does not track review-flow RAGs yet — investigate the "
                "Red findings above directly on its tab.",
                className="overview-esc-card-note",
            )
        )
    if record["Commentary"]:
        body_children.append(
            html.Div(
                className="overview-esc-card-commentary",
                children=[
                    html.Span("Reviewer sign-off", className="overview-esc-card-commentary-label"),
                    html.Blockquote(record["Commentary"], className="overview-esc-card-commentary-text"),
                ],
            )
        )
    body_children.append(
        html.A(
            f"Open {record['Model Group']} Performance →",
            href=_esc_tab_href(record, reporting_cycle, entity_key),
            className="overview-esc-card-link",
        )
    )

    return html.Details(
        className=row_class,
        children=[summary, html.Div(body_children, className="overview-esc-row-body")],
    )


def _esc_watch_row(record: dict, reporting_cycle: str, entity_key: str) -> html.Div:
    """Compact watch-list row: the worst stage (or finding) and its one-line
    playbook action -- enough to document without a full escalation card."""
    selections = record["Selections"]
    if selections:
        worst = max(selections, key=lambda selection: _ESC_RAG_RANK.get(selection["rag"], -1))
        rag = worst["rag"]
        context = f"{_ESC_STAGE_KICKERS.get(worst['stage'], worst['stage'])} · {rag}"
        line = (worst.get("action") or {}).get("required_action") or "No playbook action matches this stage yet."
    elif record["Drivers"]:
        metric, rag = record["Drivers"][0]
        display_label = _driver_display_label(metric, record)
        context = f"{display_label} · {rag}"
        line = f"{rag} finding on {display_label} — review on the tab."
    else:
        rag = record["Overall RAG"]
        context = f"Overall RAG · {rag}"
        line = "Review on the tab."
    return html.Div(
        className="overview-esc-watch-row",
        children=[
            pd_rag_dot(rag),
            html.Strong(record["Entity Label"], className="overview-esc-watch-name"),
            html.Span(context, className="overview-esc-watch-context"),
            html.Span(line, className="overview-esc-watch-action"),
            html.A("Open tab →", href=_esc_tab_href(record, reporting_cycle, entity_key), className="overview-esc-watch-link"),
        ],
    )


def _governance_next_steps_board(esc: dict, entity_noun: str, reporting_cycle: str, entity_key: str) -> html.Div:
    posture_title, tone = _esc_posture(esc, entity_noun)
    tiers, counts = esc["tiers"], esc["counts"]
    children = [
        html.Div(
            className="overview-governance-posture",
            children=[
                html.Div(
                    className="overview-governance-posture-heading",
                    children=[
                        html.Span("Current governance posture"),
                        html.H4(posture_title),
                    ],
                ),
                html.Div(
                    [_esc_tier_chip(tier, counts[tier]) for tier in ("escalate", "watch", "clear")],
                    className="overview-esc-tier-chips",
                ),
                html.P(esc["narrative"]),
            ],
        ),
    ]
    if tiers["escalate"]:
        children.append(
            html.Div(
                className="overview-esc-rows",
                children=[
                    html.Div(
                        className="overview-esc-rows-head",
                        children=[
                            html.Div(
                                f"Click a {entity_noun} to see its review flow and next steps",
                                className="overview-esc-rows-hint",
                            ),
                            # Toggles every row in this board open/closed. Handled by the
                            # overview_expand_all.js asset (native <details>, no callback).
                            html.Button(
                                "Expand all",
                                type="button",
                                className="overview-esc-expand-all",
                                **{"aria-label": "Expand or collapse all escalation cards"},
                            ),
                        ],
                    ),
                    *[_esc_row(record, reporting_cycle, entity_key) for record in tiers["escalate"]],
                ],
            )
        )
    if tiers["watch"]:
        children.append(
            html.Div(
                className="overview-esc-watch",
                children=[
                    html.Div("Watch list — action to document, no escalation", className="overview-esc-strip-title"),
                    *[_esc_watch_row(record, reporting_cycle, entity_key) for record in tiers["watch"]],
                ],
            )
        )
    if tiers["clear"]:
        children.append(
            html.Div(
                className="overview-esc-clear",
                children=[
                    html.Span("In tolerance — continue normal monitoring:", className="overview-esc-clear-label"),
                    *[html.Span(record["Entity Label"], className="overview-esc-clear-chip") for record in tiers["clear"]],
                ],
            )
        )
    return html.Div(children, className=f"section-card overview-governance-board overview-governance-board-{tone}")


def _build_governance_section(
    current_rows: list[dict], scoped_rows: list[dict], findings: list[dict], monitoring_actions: list[dict],
    reporting_cycle: str,
) -> html.Section:
    esc = escalation_next_steps(current_rows, scoped_rows, findings, monitoring_actions, entity_key="Model")
    return html.Section(
        id="overview-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.4 Model Governance Summary",
                "Escalation & Next Steps",
                "Models that require escalation, their review-flow verdicts, and the playbook actions to take "
                "next — mirroring each Performance tab's Conclusion section.",
                "N/A",
                {"show_rag": False},
            ),
            _governance_next_steps_board(esc, "model", reporting_cycle, "Model"),
        ],
    )


def _build_segment_governance_section(
    current_rows: list[dict], scoped_rows: list[dict], findings: list[dict], monitoring_actions: list[dict],
    reporting_cycle: str,
) -> html.Section:
    esc = escalation_next_steps(current_rows, scoped_rows, findings, monitoring_actions, entity_key="Segment")
    return html.Section(
        id="overview-segment-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Segment Governance Summary",
                "Escalation & Next Steps",
                "Segments that require escalation, their review-flow verdicts, and the playbook actions to take "
                "next — mirroring each Performance tab's Conclusion section.",
                "N/A",
                {"show_rag": False},
            ),
            _governance_next_steps_board(esc, "segment", reporting_cycle, "Segment"),
        ],
    )


# ---------------------------------------------------------------------------
# Content renderer
# ---------------------------------------------------------------------------


def render_overview_content(
    data: dict,
    reporting_cycle: str,
    monitoring_point: str,
    rag_trend_metric: str,
    segment_rag_trend_metric: str,
    range_store: dict | None,
    theme_value: str | None = None,
    segment_model_group: str = "All",
    selected_models: list[str] | None = None,
) -> tuple[list, list[dict], list[dict]]:
    """Returns ``(content_children, scoped_rows, segment_scoped_rows)``, cached into
    ``SCOPED_ROWS_STORE_ID`` / ``SEGMENT_SCOPED_ROWS_STORE_ID`` so each chapter's RAG-trend
    dimension/range controls can update just that chart without recomputing the whole page
    (see ``build_trend_figure`` / ``build_segment_trend_figure``)."""
    theme = normalize_theme_value(theme_value)
    range_store = range_store or {}

    scoped_rows, chapter1_exclusions = build_overview_rows(data, reporting_cycle)
    segment_scoped_rows = build_overview_segment_rows(data, reporting_cycle)
    # Post Subjective Review is cycle-level (same verdict on every quarter row
    # for an entity, per augment_rows_with_post_subjective's own docstring), so
    # this must run on every quarter in scoped_rows -- not just the resolved
    # "current" row -- otherwise the RAG Trend heatmaps see those columns as
    # unset (N/A) everywhere except whichever quarter happens to be current.
    scoped_rows = augment_rows_with_post_subjective(scoped_rows, data, reporting_cycle)
    segment_scoped_rows = augment_segment_rows_with_post_subjective(segment_scoped_rows, data, reporting_cycle)
    # Model Group filter (top filter bar) -- narrows every section of BOTH
    # chapters (1.1-1.4 Models, 2.1-2.4 Segments) down to one model group's
    # rows; "All" keeps every group, unfiltered.
    if segment_model_group and segment_model_group != "All":
        scoped_rows = [row for row in scoped_rows if row["Model Group"] == segment_model_group]
        segment_scoped_rows = [row for row in segment_scoped_rows if row["Model Group"] == segment_model_group]
        chapter1_exclusions = [row for row in chapter1_exclusions if row["Model Group"] == segment_model_group]
    # Model filter (top filter bar) -- narrows to the checked models only;
    # unset (None) means "not wired up yet" and keeps every model.
    if selected_models is not None:
        selected_model_set = set(selected_models)
        scoped_rows = [row for row in scoped_rows if row["Model"] in selected_model_set]
        segment_scoped_rows = [row for row in segment_scoped_rows if row["Model"] in selected_model_set]
        chapter1_exclusions = [row for row in chapter1_exclusions if row["Model"] in selected_model_set]
    current_rows = resolve_current_rows(scoped_rows, monitoring_point or "All")
    current_segment_rows = resolve_current_segment_rows(segment_scoped_rows, monitoring_point or "All")
    # The Models chapter now reflects only named model rows for PD, plus each
    # tab's own directly stored entities for the other model groups.
    findings = top_findings(current_rows)
    segment_findings = segment_top_findings(current_segment_rows)

    executive_summary = build_executive_summary(
        "Overview is the cross-portfolio command center for PD, LGD, EAD, and Loss model monitoring. It "
        "reuses each tab's own RAG logic — nothing is re-derived — so the picture here always agrees with what "
        "each individual Performance tab shows, rolled up into a Models chapter and a Segments chapter, each "
        "with its own RAG heatmap, trend, and governance-ready findings summary.",
        theme,
    )

    chapter_1 = build_pd_chapter_heading(
        "1.",
        "Models",
        "Cross-portfolio monitoring view combining PD, LGD, EAD, and Loss models into a single RAG posture. Every "
        "row is each model's Segment: All aggregate across the whole portfolio -- see the Segments chapter below "
        "for a per-segment breakdown.",
        options={"note": f"Model use case / cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'} · Segment: All"},
    )
    chapter_1_sections = [
        _build_summary_section(current_rows, findings, monitoring_point or "All", theme, chapter1_exclusions),
        _build_heatmap_section(current_rows, theme, monitoring_point or "All"),
        _build_trend_section(scoped_rows, rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_governance_section(current_rows, scoped_rows, findings, data.get("monitoring_actions") or [], reporting_cycle),
    ]

    chapter_2 = build_pd_chapter_heading(
        "2.",
        "Segments",
        "Every model group's book of business sliced by portfolio segment instead of by model (PD segments are "
        "broken out per model, since more than one PD model can cover the same segment name).",
        options={
            "note": f"Model use case / cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'}",
            "extra_class": "overview-chapter-heading-segments",
        },
    )
    chapter_2_sections = [
        _build_segment_summary_section(current_segment_rows, segment_findings, monitoring_point or "All", theme),
        _build_segment_heatmap_section(current_segment_rows, theme, monitoring_point or "All"),
        _build_segment_trend_section(segment_scoped_rows, segment_rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_segment_governance_section(
            current_segment_rows, segment_scoped_rows, segment_findings, data.get("monitoring_actions") or [],
            reporting_cycle,
        ),
    ]

    children = [
        html.Div(executive_summary, className="overview-executive-summary"),
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-overview", children=chapter_1_sections),
        chapter_2,
        html.Div(className="pd-chapter-body pd-chapter-body-rag", children=chapter_2_sections),
    ]
    return children, scoped_rows, segment_scoped_rows


def _build_overview_apply_button() -> html.Div:
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
                        title="Load the portfolio overview using the selected filters.",
                    ),
                ],
            ),
        ],
    )


def build_overview_apply_prompt() -> html.Section:
    return html.Section(
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    "Overview is the cross-portfolio command center for PD, LGD, EAD, and Loss model "
                    "monitoring. It reuses each tab's own RAG logic — nothing is re-derived — so the picture "
                    "here always agrees with what each individual Performance tab shows, rolled up into a "
                    "Models chapter and a Segments chapter, each with its own RAG heatmap, trend, and "
                    "governance-ready findings summary.",
                ],
            ),
            html.Div(
                className="saas-model-panel-stack",
                children=[
                    html.Div(
                        className="section-card pd-mev-empty-state saas-getting-started",
                        children=[
                            html.Div("Getting started with Overview", className="pd-mev-chart-title"),
                            html.P(
                                "Set your filters in the top bar, then click “Apply filters” to render the portfolio "
                                "overview. Use the quick guide below to move from setup to analysis smoothly.",
                                className="pd-section-subtitle",
                            ),
                            html.Div(
                                className="saas-getting-started-summary",
                                children=[
                                    html.Div("Quick start", className="saas-getting-started-summary-title"),
                                    html.Div(
                                    className="saas-getting-started-highlights",
                                    children=[
                                        html.Span("1. Optionally narrow by Model Group and Model.", className="saas-getting-started-highlight"),
                                        html.Span("2. Choose Model Use Case / Cycle and Monitoring Point.", className="saas-getting-started-highlight"),
                                        html.Span("3. Click Apply filters to load the overview.", className="saas-getting-started-highlight"),
                                    ],
                                ),
                                    html.Div(
                                        "The overview always reflects the most recent applied filter snapshot, not any unapplied edits still sitting in the top bar.",
                                        className="saas-getting-started-summary-note",
                                    ),
                                ],
                            ),
                            html.Ol(
                                className="saas-getting-started-steps",
                                children=[
                                    html.Li([
                                        html.Strong("Narrow by Model Group and Model (optional). "),
                                        "Model Group restricts everything to one workstream (PD, LGD, EAD, or Loss); "
                                        "Model then lets you check or uncheck individual models within whatever "
                                        "Model Group allows — its options narrow live as Model Group changes, and "
                                        "the “All” checkbox at the top selects or clears every visible model at "
                                        "once. Leave both at their defaults to see every model.",
                                    ]),
                                    html.Li([
                                        html.Strong("Pick a Model Use Case / Cycle. "),
                                        "LGD, EAD, and Loss keep a separate precomputed dataset per cycle (e.g. CCAR 2026); "
                                        "PD's data spans every cycle already.",
                                    ]),
                                    html.Li([
                                        html.Strong("Set the Monitoring Point. "),
                                        "Pick the as-of quarter to view across every workstream and segment.",
                                    ]),
                                    html.Li([
                                        html.Strong("Click “Apply filters”. "),
                                        "The overview loads here. Nothing renders until you apply, so this starting "
                                        "guide stays visible until the first Apply.",
                                    ]),
                                    html.Li([
                                        html.Strong("Read the analysis. "),
                                        "Once loaded, the page is organised as two parallel chapters, each with the "
                                        "same four sub-sections:",
                                        html.Ul(
                                            className="saas-getting-started-substeps",
                                            children=[
                                                html.Li([html.Strong("1. Models — "), "PD, LGD, EAD, and Loss, one row per model. Model Overview, Model RAG Heatmap, Model RAG Trend Analysis, and Model Governance Summary."]),
                                                html.Li([html.Strong("2. Segments — "), "Every model group's book of business, one row per (model group, model, portfolio segment) triple. Segment Overview, Segment RAG Heatmap, Segment RAG Trend Analysis, and Segment Governance Summary -- the same four sub-sections, sliced by segment instead of model."]),
                                            ],
                                        ),
                                    ]),
                                    html.Li([
                                        html.Strong("Jump between sections with the subnav bar. "),
                                        "Once the overview has loaded, the Models and Segments rows just below the top "
                                        "filter bar list all eight sub-sections by name -- click any of them to scroll "
                                        "straight there instead of scrolling manually.",
                                    ]),
                                    html.Li([
                                        html.Strong("Fine-tune within each section. "),
                                        "Each chapter's RAG trend chart has its own dimension picker and Window / From / To "
                                        "range controls — these do not require re-applying the top filters.",
                                    ]),
                                    html.Li([
                                        html.Strong("Start over. "),
                                        "Refresh the page at any time to clear the overview and return to this starting view.",
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


def build_layout(search: str = "") -> list:
    """Entry point for the page registry.

    ``search`` (the page's ``dcc.Location`` query string) is accepted for a
    uniform call signature across every page's ``build_layout`` -- see
    ``shell.py``'s router -- but unused here: Overview is the *source* of
    deep links (its escalation cards), never their target.
    """
    from ...data_access import PD_PERFORMANCE_DATA
    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Build the Overview page with top controls and the Apply-gated landing content."""
    from .....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    default_cycle = reporting_cycle_options[0]["value"]
    cycle_quarters = shared_filters.ALL_REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_point_options = [{"label": q, "value": q} for q in cycle_quarters]
    default_monitoring_point = shared_filters.resolve_monitoring_point_value(cycle_quarters, None)
    model_options = overview_model_options(data)
    default_models = [option["value"] for option in model_options]

    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
        dcc.Store(id=APPLIED_FILTERS_STORE_ID),
        dcc.Store(id=SCOPED_ROWS_STORE_ID),
        dcc.Store(id=SEGMENT_SCOPED_ROWS_STORE_ID),
        dcc.Store(id=RAG_FLOW_SELECTION_STORE_ID, data={"model": None, "segment": None}),
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("Wholesale Portfolio Model Monitoring Dashboard", className="monitoring-dashboard-title"),
                        html.Div(
                            className="monitoring-controls saas-top-filter-row overview-primary-filter-row",
                            children=[
                                _build_filter(
                                    "Model Group",
                                    shared_filters.build_single_select_dropdown(
                                        value_id=SEGMENT_MODEL_GROUP_ID,
                                        toggle_id=SEGMENT_MODEL_GROUP_TOGGLE_ID,
                                        menu_id=SEGMENT_MODEL_GROUP_MENU_ID,
                                        filter_key=SEGMENT_MODEL_GROUP_FILTER_KEY,
                                        options=_dropdown_options(SEGMENT_MODEL_GROUP_OPTIONS),
                                        value="All",
                                    ),
                                ),
                                _build_filter(
                                    "Model",
                                    _build_model_filter(model_options, default_models),
                                ),
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
                                        value_id=MONITORING_POINT_ID,
                                        toggle_id=MONITORING_POINT_TOGGLE_ID,
                                        menu_id=MONITORING_POINT_MENU_ID,
                                        filter_key=MONITORING_POINT_FILTER_KEY,
                                        options=monitoring_point_options,
                                        value=default_monitoring_point,
                                    ),
                                ),
                                _build_overview_apply_button(),
                            ],
                        ),
                        html.Div(style={"marginTop": "12px"}, children=[_build_overview_subnav()]),
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
                        delay_show=60,
                        children=build_overview_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
