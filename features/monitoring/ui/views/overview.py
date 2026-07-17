"""Layout for the Overview page: a cross-portfolio RAG command center.

Combines PD, LGD, EAD, and Loss into one view built directly on each tab's
own domain functions (see ``domain/overview.py``), organised as a single
chapter with five sections: RAG Assignment overview, Model RAG Heatmap,
RAG Trend Analysis, and Governance Summary.
"""

from __future__ import annotations

from collections import Counter
from textwrap import wrap

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
    FINAL_RAG_PLACEHOLDER,
    HEATMAP_COLUMNS,
    HEATMAP_FINAL_COLUMNS,
    MODEL_GROUPS,
    POST_SUBJECTIVE_COLUMNS,
    RAG_ASSIGNMENT_COLUMNS,
    RAG_COLUMNS,
    RAG_COLUMN_DESCRIPTIONS,
    available_periods,
    build_overview_rows,
    build_overview_segment_rows,
    category_breakdown,
    category_green_count,
    display_rag,
    effective_rag,
    governance_summary,
    heatmap_rows,
    models_by_overall_rag,
    overview_summary,
    periods_through,
    resolve_current_rows,
    resolve_current_segment_rows,
    segment_governance_summary,
    segment_heatmap_rows,
    segment_overview_summary,
    segments_by_overall_rag,
    segment_top_findings,
    top_findings,
)
from .cards import build_pd_chapter_heading, build_pd_section_heading
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
RAG_TREND_RANGE_KEY = "overview_rag_trend"
SEGMENT_RAG_TREND_RANGE_KEY = "overview_segment_rag_trend"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
_RAG_FLOW_STAGES = [
    ("Overall RAG", "Performance RAG"),
    ("Post Subjective Review RAG", "Post Subjective Review RAG"),
    ("Pre Mitigation RAG", "Pre Mitigation RAG"),
    ("Post Mitigation RAG", "Post Mitigation RAG"),
]
_RAG_FLOW_STAGE_X = [0.05, 0.35, 0.65, 0.95]
_RAG_FLOW_TONE_Y = {"Green": 0.06, "Amber": 0.31, "Red": 0.56, "N/A": 0.81}
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
    scenarios = load_filter_config().get("scenarios") or []
    return scenarios[0]["value"] if scenarios else "intsevere"


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
    }


def _lgd_ead_post_subjective_rag(data: dict, model_type: str, sensitivity_key: str, entity: str, reporting_cycle: str, scenario: str, level: str = "model") -> dict[str, str]:
    """``entity`` is a model name when ``level == "model"`` (Models chapter),
    or a segment name when ``level == "segment"``
    (Segments chapter) -- mirrors the ``(level, value)`` scoping each tab's
    own sensitivity-projections and MEV catalog already support."""
    from .post_subjective import (
        PostSubjectiveConfig, _fmt_pct, _impact_summary, _mev_range_summary, _projection_rows,
        _scenario_ranking_summary, _sensitivity_threshold, resolve_scenario_selection,
    )

    cfg = PostSubjectiveConfig(
        prefix=model_type.lower(), label=model_type, model_type=model_type,
        sensitivity_key=sensitivity_key, scenario_filter_id="overview-unused",
    )
    all_rows = _projection_rows(data.get(sensitivity_key) or [], reporting_cycle, level, entity)
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
        mev_summary = _mev_range_summary(cfg, data, "All", entity, reporting_cycle, scenario)
    else:
        mev_summary = _mev_range_summary(cfg, data, entity, "All", reporting_cycle, scenario)
    return {
        "Transition Matrix RAG": "N/A",
        "Transition Matrix Metric": "—",
        "Scenario Ranking RAG": scenario_ranking_rag,
        "Scenario Ranking Metric": scenario_ranking_metric,
        "Sensitivity Analysis RAG": sensitivity_rag,
        "Sensitivity Analysis Metric": sensitivity_metric,
        "MEV Range RAG": mev_summary["rag"],
        "MEV Range Metric": mev_summary["metric"],
    }


def augment_rows_with_post_subjective(rows: list[dict], data: dict, reporting_cycle: str) -> list[dict]:
    """Merge Transition Matrix / Scenario Ranking / Sensitivity / MEV Range RAG onto
    each row, keyed by (Model Group, Model, Segment) so every quarter row for a
    given model within this reporting cycle carries the same cycle-level verdict."""
    scenario = _default_scenario(data)
    sidecar: dict[tuple[str, str, str], dict[str, str]] = {}

    pd_keys = {(row["Model"], row.get("Segment", "All")) for row in rows if row["Model Group"] == "PD"}
    for model, segment in pd_keys:
        # ctx uses lowercase "all" for the pooled/Segment: All case, matching
        # the PD Performance tab's own convention (see _ctx_store_keys).
        ctx_segment = "all" if segment == "All" else segment
        models = {model}
        sidecar[("PD", model, segment)] = _pd_post_subjective_rag(data, models, ctx_segment, reporting_cycle, scenario)
    # Sourced from ``rows`` itself so the sidecar stays aligned with whatever
    # model rows the Overview page is currently surfacing for LGD and EAD.
    lgd_models = {row["Model"] for row in rows if row["Model Group"] == "LGD"}
    ead_models = {row["Model"] for row in rows if row["Model Group"] == "EAD"}
    for model in lgd_models:
        sidecar[("LGD", model, "All")] = _lgd_ead_post_subjective_rag(data, "LGD", "lgd_sensitivity_projections", model, reporting_cycle, scenario)
    for model in ead_models:
        sidecar[("EAD", model, "All")] = _lgd_ead_post_subjective_rag(data, "EAD", "ead_sensitivity_projections", model, reporting_cycle, scenario)

    for row in rows:
        key = (row["Model Group"], row["Model"], row.get("Segment", "All"))
        row.update(sidecar.get(key, {}))
    return rows


def augment_segment_rows_with_post_subjective(rows: list[dict], data: dict, reporting_cycle: str) -> list[dict]:
    """Segments-chapter equivalent of ``augment_rows_with_post_subjective``,
    keyed by (Model Group, Segment): PD pools every PD model per segment
    (there's no single "model" to key off of), while LGD/EAD look up their
    own per-segment sensitivity/MEV data directly (see
    _lgd_ead_post_subjective_rag's ``level="segment"``). Loss has no Post
    Subjective Review columns, so it's left out entirely."""
    scenario = _default_scenario(data)
    all_pd_models = set(data.get("model_names", []))
    sidecar: dict[tuple[str, str], dict[str, str]] = {}
    for segment in {row["Segment"] for row in rows if row["Model Group"] == "PD"}:
        sidecar[("PD", segment)] = _pd_post_subjective_rag(data, all_pd_models, segment, reporting_cycle, scenario)
    for segment in {row["Segment"] for row in rows if row["Model Group"] == "LGD"}:
        sidecar[("LGD", segment)] = _lgd_ead_post_subjective_rag(data, "LGD", "lgd_sensitivity_projections", segment, reporting_cycle, scenario, level="segment")
    for segment in {row["Segment"] for row in rows if row["Model Group"] == "EAD"}:
        sidecar[("EAD", segment)] = _lgd_ead_post_subjective_rag(data, "EAD", "ead_sensitivity_projections", segment, reporting_cycle, scenario, level="segment")
    for row in rows:
        row.update(sidecar.get((row["Model Group"], row["Segment"]), {}))
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
                            _subnav_link("overview-summary", "Overview", active=True),
                            _subnav_link("overview-heatmap", "Model RAG Heatmap"),
                            _subnav_link("overview-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-governance-summary", "Governance Summary"),
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
                            _subnav_link("overview-segment-summary", "Overview"),
                            _subnav_link("overview-segment-heatmap", "Segment RAG Heatmap"),
                            _subnav_link("overview-segment-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-segment-governance-summary", "Governance Summary"),
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


def _rag_flow_entity_label(row: dict) -> str:
    group = str(row.get("Model Group", "") or "").strip()
    model = str(row.get("Model", "") or "").strip()
    segment = str(row.get("Segment", "") or "").strip()
    entity = model or segment or group
    if group and entity and not entity.lower().startswith(group.lower()):
        return f"{group} {entity}"
    return entity or group


def _format_rag_flow_entities(labels: list[str], max_items: int = 6, separator: str = ", ") -> str:
    clean = [str(label).strip() for label in labels if str(label).strip()]
    if not clean:
        return "None"
    ordered = sorted(dict.fromkeys(clean))
    if len(ordered) <= max_items:
        return separator.join(ordered)
    return separator.join(ordered[:max_items]) + f"{separator}+{len(ordered) - max_items} more"


def _rag_flow_help_chip() -> html.Div:
    definitions = [
        ("Performance RAG", "Based on the results of tests applied at the modelled outcomes."),
        ("Post Subjective Review", "Reflects the impact of any subjective overlays and considers the post-subjective review."),
        ("Pre Mitigation", "Pre-Overlay RAG obtained from the trend of the post-subjective-review model RAG."),
        ("Post Mitigation", "Post-Overlay RAG based on the residual risk of the model, including compensating controls."),
    ]
    return html.Div(
        className="overview-help",
        children=[
            html.Button(
                "i",
                type="button",
                className="overview-help-chip",
                title="RAG definitions",
                **{"aria-label": "Show RAG migration journey definitions"},
            ),
            html.Div(
                className="overview-help-tooltip overview-help-tooltip-rag-flow",
                children=[
                    html.Div("RAG definitions", className="overview-help-tooltip-title"),
                    html.Div(
                        className="overview-help-tooltip-list",
                        children=[
                            html.Div(
                                className="overview-help-tooltip-item",
                                children=[
                                    html.Strong(label),
                                    html.Span(copy),
                                ],
                            )
                            for label, copy in definitions
                        ],
                    ),
                ],
            ),
        ],
    )


def _wrap_rag_flow_label(label: str, max_chars: int) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    parts = wrap(text, width=max_chars, break_long_words=True, break_on_hyphens=True)
    return "<br>".join(parts)


def _rag_flow_label_layout(flow_rows: list[dict[str, object]], compact: bool = False) -> tuple[dict[str, str], int, int]:
    wrap_width = 16 if compact else 20
    wrapped_labels: dict[str, str] = {}
    max_line_chars = 0
    max_lines = 1
    for row in flow_rows:
        raw_label = str(row.get("Entity Label", "") or "")
        wrapped = _wrap_rag_flow_label(raw_label, wrap_width)
        wrapped_labels[raw_label] = wrapped
        lines = wrapped.split("<br>") if wrapped else [""]
        max_lines = max(max_lines, len(lines))
        max_line_chars = max(max_line_chars, max((len(line) for line in lines), default=0))
    return wrapped_labels, max_line_chars, max_lines


def _rag_flow_chart_height(flow_rows: list[dict[str, object]], compact: bool = False) -> int:
    # The default chart is aggregated by RAG bucket, so its height should not
    # grow with the number of models in scope. Model names live in the
    # scrollable journey browser and only the selected path is labelled.
    return 480 if compact else 460


def _rag_flow_models(current_rows: list[dict]) -> list[dict[str, object]]:
    flow_rows: list[dict[str, object]] = []
    for row in current_rows:
        entity_label = _rag_flow_entity_label(row)
        if not entity_label:
            continue
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
    }


def _rag_flow_selection_rows(
    flow_rows: list[dict[str, object]],
    selection: dict[str, object] | None,
) -> list[dict[str, object]]:
    if not selection:
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
    flow_rows = _rag_flow_models(current_rows)
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
            ],
        )

    stage_index = int(selection.get("stage_index", 0))
    tone = str(selection.get("tone", "N/A"))
    active_entity = str(selection.get("entity", "") or "")
    stage_label = _RAG_FLOW_STAGES[stage_index][1]
    ordered_rows = sorted(selected_rows, key=lambda row: str(row.get("Entity Label", "")).lower())
    periods = sorted({
        str(row.get("Monitoring Period", "") or "").strip()
        for row in ordered_rows
        if str(row.get("Monitoring Period", "") or "").strip()
    })
    period_copy = periods[0] if len(periods) == 1 else (", ".join(periods) if periods else "current selection")

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
                            html.Strong(f"{stage_label} · {tone}"),
                            html.P(
                                f"Only complete journeys available in the current filtered data are shown. "
                                f"Select a {entity_label} below to highlight its recorded path."
                            ),
                        ],
                    ),
                    html.Button(
                        "Back to portfolio view",
                        id={"type": RAG_FLOW_RESET_BUTTON_TYPE, "scope": scope},
                        n_clicks=0,
                        type="button",
                        className="overview-rag-flow-reset",
                    ),
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
                                    for (_, stage_name), tone_value in zip(_RAG_FLOW_STAGES, row["tones"])
                                ],
                            ),
                        ],
                    )
                    for row in ordered_rows
                ],
            ),
        ],
    )


def _final_post_mitigation_distribution_card(current_rows: list[dict], entity_kind: str = "model") -> html.Div:
    is_segment = entity_kind == "segment"
    summary = segment_overview_summary(current_rows) if is_segment else overview_summary(current_rows)
    flow_rows = _rag_flow_models(current_rows)
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

    loss_rows = [row for row in current_rows if row.get("Model Group") == "Loss"]
    loss_models = []
    for row in loss_rows:
        label = _rag_flow_entity_label(row)
        loss_models.append(f"{label} · {display_rag(row.get('Overall RAG'))}")
    loss_models = _ordered_unique(loss_models)
    loss_worst = "Green"
    if loss_rows:
        severity = {"Green": 1, "Amber": 2, "Red": 3, "N/A": 2}
        loss_worst = max(
            (effective_rag(row.get("Overall RAG")) for row in loss_rows),
            key=lambda rag: severity.get(rag, 2),
            default="Green",
        )

    return html.Div(
        className="section-card overview-summary-final-post-mitigation",
        children=[
            build_chart_header(
                "Post Mitigation Distribution",
                "Post Mitigation is treated as the final portfolio outcome for models with review coverage; Loss remains performance-only.",
            ),
            html.Div(
                className="overview-hero-kpis overview-summary-kpis",
                children=[
                    _hero_kpi(
                        summary["segments"] if is_segment else summary["models"],
                        "Segments monitored" if is_segment else "Models monitored",
                        "blue",
                        description="Across every model group" if is_segment else "Across PD, LGD, EAD, and Loss",
                    ),
                    _hero_kpi(len(red_models), "Final Red", "Red", items=red_models or ["None in scope"]),
                    _hero_kpi(len(amber_models), "Final Amber", "Amber", items=amber_models or ["None in scope"]),
                    _hero_kpi(len(green_models), "Final Green", "Green", items=green_models or ["None in scope"]),
                    _hero_kpi(
                        len(loss_models),
                        "Loss performance-only",
                        loss_worst,
                        items=loss_models or ["No Loss models in scope"],
                    ),
                ],
            ),
        ],
    )


def _rag_flow_summary_card(current_rows: list[dict], theme: str, entity_kind: str = "model") -> html.Div:
    rag_flow_summary = _rag_flow_summary(_rag_flow_models(current_rows))
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
            build_chart_header(
                title,
                header_copy,
                extra_controls=_rag_flow_help_chip(),
            ),
            html.Div(
                className="overview-rag-flow-graphs",
                children=[
                    dcc.Graph(
                        id=desktop_graph_id,
                        className="overview-rag-flow-graph overview-rag-flow-graph-desktop",
                        figure=_rag_flow_sankey_figure(current_rows, theme, entity_kind=entity_kind),
                        config=_GRAPH_CONFIG,
                        style={"height": f"{_rag_flow_chart_height(_rag_flow_models(current_rows))}px"},
                    ),
                    dcc.Graph(
                        id=compact_graph_id,
                        className="overview-rag-flow-graph overview-rag-flow-graph-compact",
                        figure=_rag_flow_sankey_figure(current_rows, theme, compact=True, entity_kind=entity_kind),
                        config=_GRAPH_CONFIG,
                        style={"height": f"{_rag_flow_chart_height(_rag_flow_models(current_rows), compact=True)}px"},
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
                            f"({rag_flow_summary['pd_models']} PD, {rag_flow_summary['lgd_models']} LGD, {rag_flow_summary['ead_models']} EAD)"
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
    flow_rows = _rag_flow_models(current_rows)
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
    muted_color = "#94a3b8" if is_dark else "#64748b"
    stage_positions = [0.24, 1.12, 2.0, 2.88] if compact else [0.18, 1.08, 1.98, 2.88]
    stage_font_size = 12 if compact else 14
    tone_font_size = 13 if compact else 15
    stage_label_y = 0.955 if compact else 0.962
    left_label_room = 0.66 if compact else 0.72
    right_label_room = 0.42 if compact else 0.48
    margin = dict(t=22, r=26, b=6, l=50) if compact else dict(t=26, r=30, b=8, l=60)
    x_axis_range = [stage_positions[0] - left_label_room, stage_positions[-1] + right_label_room]
    tone_label_x = x_axis_range[0] + (0.05 if compact else 0.06)
    band_x0 = tone_label_x + (0.18 if compact else 0.22)
    fig = go.Figure()

    tone_centers = {
        tone: (_RAG_FLOW_BAND_RANGES[tone][0] + _RAG_FLOW_BAND_RANGES[tone][1]) / 2
        for tone in _RAG_FLOW_TONE_ORDER
    }
    stage_counts = {
        stage_index: Counter(
            row["tones"][stage_index]
            for row in selected_rows
            if isinstance(row.get("tones"), list) and len(row["tones"]) == len(_RAG_FLOW_STAGES)
        )
        for stage_index in range(len(_RAG_FLOW_STAGES))
    }
    transition_counts = {
        stage_index: Counter(
            (row["tones"][stage_index], row["tones"][stage_index + 1])
            for row in selected_rows
            if isinstance(row.get("tones"), list) and len(row["tones"]) == len(_RAG_FLOW_STAGES)
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
        y_positions = [
            tone_centers[tone] + (0.032 if stage_index % 2 == 0 else -0.032)
            for stage_index, tone in enumerate(tones)
        ]
        for stage_index in range(len(_RAG_FLOW_STAGES) - 1):
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
            for stage_index, xanchor, xshift, align in (
                (0, "right", -20, "right"),
                (len(_RAG_FLOW_STAGES) - 1, "left", 13, "left"),
            )
        ]
        fig.add_trace(go.Scatter(
            x=stage_positions,
            y=y_positions,
            mode="markers",
            marker=dict(
                size=17 if compact else 19,
                color=[marker_colors[tone] for tone in tones],
                line=dict(width=0),
            ),
            customdata=[
                ["rag-entity", active_entity, _RAG_FLOW_STAGES[index][1], tone]
                for index, tone in enumerate(tones)
            ],
            hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[2]}: %{customdata[3]}<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        height=height,
        margin=margin,
        font=dict(size=12, color=text_color),
        annotations=[
            dict(
                x=stage_positions[index],
                y=stage_label_y,
                xref="x",
                yref="paper",
                text=label,
                showarrow=False,
                font=dict(size=stage_font_size, color=muted_color),
            )
            for index, (_, label) in enumerate(_RAG_FLOW_STAGES)
        ] + [
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
                    text=(
                        f"Focused view · {len(selected_rows)} {entity_label}(s) from "
                        f"{_RAG_FLOW_STAGES[int(selection['stage_index'])][1]} · {selection['tone']}"
                    ),
                    showarrow=False,
                    font=dict(size=10 if compact else 11, color=palette["focus_text"]),
                )
            ]
            if selection
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
                y1=0.93,
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
        yaxis=dict(range=[0.0, 1.0], visible=False, fixedrange=True),
    )
    _apply_transparent_background(fig)
    return fig


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
            custom_row.append([row["Model Group"], row["Model"], _heatmap_display_label(column), display_rag(rag), row.get("Monitoring Period", ""), metric_hover])
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
            "%{customdata[5]}"
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
    model_keys = sorted(
        {(row["Model Group"], row["Model"]) for row in rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )
    height = _rag_trend_heatmap_height(model_keys)
    all_periods = available_periods(rows)
    periods = [p for p in all_periods if visible_periods is None or p in set(visible_periods)]
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
    (Model Group, Segment) instead of per model. Keeps the same margins as
    the model heatmap (rather than shrinking the left margin for shorter
    labels) so both chapters share the same ``_heatmap_panel``/column-header
    CSS."""
    height = heatmap_chart_height(rows)
    if not rows:
        return _empty_figure("No segments are in scope for the selected filters.", height=height, theme=theme)

    y_labels = [f"{row['Model Group']} · {row['Segment']}" for row in rows]
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
            custom_row.append([row["Model Group"], row["Segment"], _heatmap_display_label(column), display_rag(rag), row.get("Monitoring Period", ""), metric_hover])
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
            "%{customdata[0]} — %{customdata[1]}<br>%{customdata[2]}: %{customdata[3]}"
            "%{customdata[5]}"
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
    """Segments-chapter equivalent of ``_rag_trend_heatmap_figure``."""
    segment_keys = sorted(
        {(row["Model Group"], row["Segment"]) for row in rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )
    height = _segment_trend_heatmap_height(segment_keys)
    all_periods = available_periods(rows)
    periods = [p for p in all_periods if visible_periods is None or p in set(visible_periods)]
    if not segment_keys or not periods:
        return _empty_figure("No RAG trend data is available for the selected filters.", height=height, theme=theme)

    by_key_period = {(row["Model Group"], row["Segment"], row["Monitoring Period"]): row.get(rag_column, "N/A") for row in rows}
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    y_labels = [f"{group} · {segment}" for group, segment in segment_keys]
    z_values, customdata = [], []
    for group, segment in segment_keys:
        z_row, custom_row = [], []
        for period in periods:
            rag = by_key_period.get((group, segment, period), "N/A")
            z_row.append(heatmap_z.get(rag, 0))
            custom_row.append([group, segment, display_rag(rag), period])
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


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _build_summary_section(current_rows: list[dict], findings: list[dict], monitoring_point: str, theme: str) -> html.Section:
    summary = overview_summary(current_rows)

    return html.Section(
        id="overview-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Overview",
                "RAG Assignment Overview",
                "",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            _final_post_mitigation_distribution_card(current_rows),
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
                "2.1 Overview",
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
                "per model group per segment (PD pooled across both PD models).",
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
                "1.3 RAG Trend Analysis",
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
    segment_keys = sorted({(row["Model Group"], row["Segment"]) for row in rows})

    return html.Section(
        id="overview-segment-rag-trend",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.3 RAG Trend Analysis",
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


def _governance_posture(gov: dict, entity_label: str) -> tuple[str, str, str]:
    total = gov["total"]
    escalation_count = len(gov["escalations"])
    plural = entity_label if escalation_count == 1 else f"{entity_label}s"
    if total == 0:
        return "No data in scope", f"No {entity_label}s match the selected filters.", "neutral"
    if escalation_count:
        return "Escalation required", f"{escalation_count} {plural} Red on at least one test", "red"
    if gov["breaches"]:
        return "Review required", f"{gov['breaches']} {entity_label}s have a Red or Amber Overall RAG", "amber"
    return "In tolerance", f"All {total} {entity_label}s are Green", "green"


def _governance_stat_row(title: str, count_text: str, bar_segments: list, meta_children: list, aria_label: str) -> html.Div:
    """One row of the governance stats strip -- label + count heading, a
    colored bar, and a muted meta line. Shared shape for both the plain
    entity-level facts (Immediate escalation, Clear models) and the RAG
    Assignment / Post Subjective Review severity comparison, so the whole
    strip reads as one consistent block instead of two different styles."""
    return html.Div(
        className="overview-governance-stat-row",
        children=[
            html.Div(
                className="overview-governance-stat-heading",
                children=[
                    html.Span(title, className="overview-governance-stat-label"),
                    html.Strong(count_text, className="overview-governance-stat-count"),
                ],
            ),
            html.Div(bar_segments, className="overview-governance-stat-bar", role="img", **{"aria-label": aria_label}),
            html.Div(meta_children, className="overview-governance-stat-meta"),
        ],
    )


def _governance_hero_stat_row(title: str, count_text: str, description: str, tone: str) -> html.Div:
    """Immediate escalation / Clear models(-segments) -- a big headline
    number rather than a bar, since each is a single count with no Red:Amber
    mix to visualize; kept in the same row wrapper as the severity rows below
    so the whole strip still shares one bordered block and grid rhythm."""
    return html.Div(
        className="overview-governance-stat-row overview-governance-stat-row-hero",
        children=[
            html.Span(title, className="overview-governance-stat-label"),
            html.Strong(count_text, className=f"overview-governance-hero-value overview-governance-hero-value-{tone}"),
            html.Span(description, className="overview-governance-stat-meta"),
        ],
    )


def _governance_severity_stat_row(title: str, breakdown: dict, green: int | None = None) -> html.Div:
    """RAG Assignment / Post Subjective Review -- bar fill is the Red:Amber
    mix *within that column family's own breaches* (not a share of all
    models), so it reads as "how severe are this category's findings",
    paired with its leading driver. ``green`` is optional: when given, a
    Green segment is added to the bar so the mix reflects every check run in
    this category, not just the ones that came back Red/Amber."""
    red, amber, breaches = breakdown["red"], breakdown["amber"], breakdown["breaches"]
    top_metric = breakdown["top_metric"] if breakdown["top_metric"] != "None" else "No findings"
    driver_count = breakdown["top_metric_count"]
    total = breaches + (green or 0)

    if total:
        bar_segments = [
            html.Span(
                className=f"overview-governance-stat-segment overview-governance-stat-segment-{tone}",
                style={"width": f"{100 * count / total:.2f}%"},
            )
            for tone, count in (("red", red), ("amber", amber), ("green", green or 0))
            if count
        ]
        breakdown_text = f"{red} Red · {amber} Amber" + (f" · {green} Green" if green is not None else "")
    else:
        bar_segments = [html.Span(className="overview-governance-stat-segment overview-governance-stat-segment-empty")]
        breakdown_text = "No breaches this period"

    meta_children = [
        html.Span(breakdown_text),
        html.Span(
            [
                "Leading driver ",
                html.Strong(top_metric),
                f" · {driver_count} open finding{'' if driver_count == 1 else 's'}" if driver_count else "",
            ],
        ),
    ]
    aria_label = f"{title}: {red} Red, {amber} Amber" + (f", {green} Green" if green is not None else "") + "."
    return _governance_stat_row(
        title, f"{breaches} breach{'' if breaches == 1 else 'es'}", bar_segments, meta_children, aria_label,
    )


def _final_rag_distribution_row(total_entities: int, entity_label: str = "model") -> html.Div:
    """Final RAG is a static placeholder (see FINAL_RAG_PLACEHOLDER) until the
    real methodology is defined -- every model/segment currently carries the
    same value, so this bar is a single segment until that changes."""
    tone = pd_tone_class(FINAL_RAG_PLACEHOLDER)
    if total_entities:
        bar_segments = [html.Span(className=f"overview-governance-stat-segment overview-governance-stat-segment-{tone}")]
        breakdown_text = f"{total_entities} {FINAL_RAG_PLACEHOLDER}"
    else:
        bar_segments = [html.Span(className="overview-governance-stat-segment overview-governance-stat-segment-empty")]
        breakdown_text = f"No {entity_label}s in scope"

    return _governance_stat_row(
        "Final RAG distribution",
        f"{total_entities} {entity_label}{'' if total_entities == 1 else 's'}",
        bar_segments,
        [html.Span(breakdown_text), html.Span("Placeholder verdict -- methodology not yet defined")],
        f"Final RAG distribution: {breakdown_text}.",
    )


def _governance_driver_chip(driver: str, driver_rags: dict[str, str]) -> html.Span:
    return html.Span(
        driver,
        className=f"overview-governance-driver-chip overview-governance-driver-chip-{pd_tone_class(driver_rags.get(driver, 'Red'))}",
    )


def _escalation_table(rows_by_group: dict[str, list[dict]], entity_label: str) -> html.Div:
    """A CSS-grid table: MODEL GROUP | {MODEL/SEGMENT} | RAG ASSIGNMENT | POST
    SUBJECTIVE REVIEW. Each group's sidebar cell uses ``gridRow: span N`` so it visually
    spans all of that group's rows -- CSS Grid auto-placement then flows the remaining
    three cells per entity into the columns beside it, group by group."""
    entity_col_label = "MODEL" if entity_label == "model" else "SEGMENT"
    cells = [
        html.Div("MODEL GROUP", className="overview-escalation-th"),
        html.Div(entity_col_label, className="overview-escalation-th"),
        html.Div("RAG ASSIGNMENT", className="overview-escalation-th"),
        html.Div("POST SUBJECTIVE REVIEW", className="overview-escalation-th"),
    ]
    for group in MODEL_GROUPS:
        group_rows = rows_by_group.get(group)
        if not group_rows:
            continue
        cells.append(
            html.Div(
                className="overview-escalation-sidebar",
                style={"gridRow": f"span {len(group_rows)}"},
                children=[
                    html.Strong(group, className="overview-escalation-sidebar-code"),
                ],
            )
        )
        for row in group_rows:
            entity_name = row["Model"] if entity_label == "model" else row["Segment"]
            drivers = [driver.strip() for driver in row["Drivers"].split(",") if driver.strip()]
            driver_rags = row.get("DriverRags", {})
            # Drivers already arrive in priority order (Overall RAG, then the
            # RAG Assignment tests that derive it, then Post Subjective
            # Review) -- split by column instead of by visual tier now that
            # each has its own dedicated column.
            assignment_drivers = [d for d in drivers if d not in POST_SUBJECTIVE_COLUMNS]
            review_drivers = [d for d in drivers if d in POST_SUBJECTIVE_COLUMNS]
            cells.append(
                html.Div(
                    children=[html.Strong(entity_name)],
                    className="overview-escalation-cell overview-escalation-model-cell",
                )
            )
            cells.append(
                html.Div(
                    [_governance_driver_chip(driver, driver_rags) for driver in assignment_drivers] or "—",
                    className="overview-escalation-cell overview-escalation-chip-cell",
                )
            )
            cells.append(
                html.Div(
                    [_governance_driver_chip(driver, driver_rags) for driver in review_drivers] or "—",
                    className="overview-escalation-cell overview-escalation-chip-cell",
                )
            )
    return html.Div(cells, className="overview-escalation-table")


def _governance_action_register(gov: dict, entity_label: str) -> html.Div:
    rows = gov["escalations"]

    # Grouped by Model Group (PD, LGD, EAD, Loss -- whichever have escalations
    # this period), each rendered as its own "tier" in the table below.
    rows_by_group: dict[str, list[dict]] = {}
    for row in rows:
        rows_by_group.setdefault(row["Model Group"], []).append(row)

    if rows:
        periods = {row["Monitoring Period"] for row in rows}
        title_text = (
            f"Escalation Register — {next(iter(periods))}"
            if len(periods) == 1
            else "Escalation Register"
        )
        body = [_escalation_table(rows_by_group, entity_label)]
    else:
        title_text = "Escalation Register"
        body = [
            html.Div(
                className="overview-governance-all-clear",
                children=[
                    html.Span(className="overview-governance-all-clear-mark", **{"aria-hidden": "true"}),
                    html.Div(
                        children=[
                            html.Strong("No immediate escalations"),
                            html.Span(f"No {entity_label}s are Red on an underlying test for the selected period."),
                        ],
                    ),
                ],
            )
        ]

    return html.Div(
        className="overview-governance-actions",
        children=[
            html.Div(
                className="overview-escalation-banner",
                children=[
                    html.Span("Required action", className="overview-escalation-banner-kicker"),
                    html.Strong(title_text, className="overview-escalation-banner-title"),
                ],
            ),
            *body,
        ],
    )


def _governance_board(
    gov: dict, entity_label: str, clean_key: str, clean_label: str, clean_unit_plural: str, show_amber_stat: bool = False,
) -> html.Div:
    posture_title, _, tone = _governance_posture(gov, entity_label)
    clean_entities = gov[clean_key]
    clean_description = ", ".join(clean_entities) if clean_entities else "None fully clear"
    # clean_unit_plural is passed explicitly (e.g. "models", "workstreams",
    # "segments") rather than derived from clean_label's wording, since the
    # label is just a display title and shouldn't have to literally name the
    # counted entity (e.g. "No findings" as a label still counts models).
    clean_unit = clean_unit_plural[:-1] if len(clean_entities) == 1 and clean_unit_plural.endswith("s") else clean_unit_plural

    if show_amber_stat:
        amber_count = gov["amber"]
        second_stat = _governance_hero_stat_row(
            "Amber findings",
            f"{amber_count} {entity_label}{'' if amber_count == 1 else 's'}",
            "Amber on Overall RAG, not yet Red",
            "amber" if amber_count else "green",
        )
    else:
        second_stat = _governance_hero_stat_row(clean_label, f"{len(clean_entities)} {clean_unit}", clean_description, "green")

    return html.Div(
        className=f"section-card overview-governance-board overview-governance-board-{tone}",
        children=[
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
                    html.P(gov["narrative"]),
                ],
            ),
            html.Div(
                className="overview-governance-stats",
                children=[
                    _governance_hero_stat_row(
                        "Immediate escalation",
                        f"{len(gov['escalations'])} {entity_label}{'' if len(gov['escalations']) == 1 else 's'}",
                        "Red on any test",
                        "red" if gov["escalations"] else "green",
                    ),
                    second_stat,
                    _governance_severity_stat_row("RAG Assignment", gov["rag_assignment"]),
                    _governance_severity_stat_row("Post Subjective Review", gov["post_subjective_review"]),
                ],
            ),
            _governance_action_register(gov, entity_label),
        ],
    )


def _build_governance_section(current_rows: list[dict], findings: list[dict]) -> html.Section:
    gov = governance_summary(current_rows, findings)
    return html.Section(
        id="overview-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.4 Governance Summary",
                "Decision Summary",
                "A concise governance posture, the signals driving it, and the actions requiring attention.",
                "Green",
                {"show_rag": False},
            ),
            _governance_board(gov, "model", "clean_models", "No findings", "models", show_amber_stat=True),
        ],
    )


def _build_segment_governance_section(current_rows: list[dict], findings: list[dict]) -> html.Section:
    gov = segment_governance_summary(current_rows, findings)
    return html.Section(
        id="overview-segment-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Governance Summary",
                "Decision Summary",
                "A concise segment-level posture, the signals driving it, and the actions requiring attention.",
                "Green",
                {"show_rag": False},
            ),
            _governance_board(gov, "segment", "clean_segments", "Clear segments", "segments"),
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
) -> tuple[list, list[dict], list[dict]]:
    """Returns ``(content_children, scoped_rows, segment_scoped_rows)``, cached into
    ``SCOPED_ROWS_STORE_ID`` / ``SEGMENT_SCOPED_ROWS_STORE_ID`` so each chapter's RAG-trend
    dimension/range controls can update just that chart without recomputing the whole page
    (see ``build_trend_figure`` / ``build_segment_trend_figure``)."""
    theme = normalize_theme_value(theme_value)
    range_store = range_store or {}

    scoped_rows = build_overview_rows(data, reporting_cycle)
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
        "Cross-portfolio monitoring view combining PD, LGD, EAD, and Loss models into a single RAG posture.",
        options={"note": f"Model use case / cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'}"},
    )
    chapter_1_sections = [
        _build_summary_section(current_rows, findings, monitoring_point or "All", theme),
        _build_heatmap_section(current_rows, theme, monitoring_point or "All"),
        _build_trend_section(scoped_rows, rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_governance_section(current_rows, findings),
    ]

    chapter_2 = build_pd_chapter_heading(
        "2.",
        "Segments",
        "Every model group's book of business sliced by portfolio segment instead of by model (PD pooled across "
        "both PD models).",
        options={
            "note": f"Model use case / cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'}",
            "extra_class": "overview-chapter-heading-segments",
        },
    )
    chapter_2_sections = [
        _build_segment_summary_section(current_segment_rows, segment_findings, monitoring_point or "All", theme),
        _build_segment_heatmap_section(current_segment_rows, theme, monitoring_point or "All"),
        _build_segment_trend_section(segment_scoped_rows, segment_rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_segment_governance_section(current_segment_rows, segment_findings),
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
                                        html.Span("1. Choose Model Use Case / Cycle and Monitoring Point.", className="saas-getting-started-highlight"),
                                        html.Span("2. Click Apply filters to load the overview.", className="saas-getting-started-highlight"),
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
                                                html.Li([html.Strong("1. Models — "), "PD, LGD, EAD, and Loss, one row per model. Overview, Model RAG Heatmap, RAG Trend Analysis, and Governance Summary."]),
                                                html.Li([html.Strong("2. Segments — "), "Every model group's book of business, one row per (model group, portfolio segment) pair (PD pooled across both PD models). The same four sub-sections, sliced by segment instead of model."]),
                                            ],
                                        ),
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


def build_layout() -> list:
    """No-arg entry point for the page registry."""
    from ...data_access import PD_PERFORMANCE_DATA
    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Build the Overview page with top controls and the Apply-gated landing content."""
    from .....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_point_options = [{"label": q, "value": q} for q in cycle_quarters]
    default_monitoring_point = shared_filters.resolve_monitoring_point_value(cycle_quarters, None)

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
                                        value_id=MONITORING_POINT_ID,
                                        toggle_id=MONITORING_POINT_TOGGLE_ID,
                                        menu_id=MONITORING_POINT_MENU_ID,
                                        filter_key=MONITORING_POINT_FILTER_KEY,
                                        options=monitoring_point_options,
                                        value=default_monitoring_point,
                                    ),
                                ),
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
