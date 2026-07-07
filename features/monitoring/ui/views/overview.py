"""Layout for the Overview page: a cross-portfolio RAG command center.

Combines PD, LGD, EAD, and Loss into one view built directly on each tab's
own domain functions (see ``domain/overview.py``), organised as a single
chapter with five sections: RAG Assignment overview, Model RAG Heatmap,
RAG Trend Analysis, and Governance Summary.
"""

from __future__ import annotations

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
from ...domain.overview import (
    FINAL_RAG_COLUMN,
    FINAL_RAG_PLACEHOLDER,
    HEATMAP_COLUMNS,
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
from .cards import _info_chip, build_pd_chapter_heading, build_pd_section_heading
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
RAG_TREND_RANGE_KEY = "overview_rag_trend"
SEGMENT_RAG_TREND_RANGE_KEY = "overview_segment_rag_trend"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


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
    (matching the tab's "Specific Models: All models" default) while the
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
    """``entity`` is a model name when ``level == "model"`` (Models chapter /
    "All Models" row), or a segment name when ``level == "segment"``
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
    all_pd_models = set(data.get("model_names", []))
    for model, segment in pd_keys:
        # ctx uses lowercase "all" for the pooled/Segment: All case, matching
        # the PD Performance tab's own convention (see _ctx_store_keys).
        # "All Models" itself isn't a real model to look up -- it means pool
        # every named model, same as _pd_rows' own "All Models" row.
        ctx_segment = "all" if segment == "All" else segment
        models = all_pd_models if model == "All Models" else {model}
        sidecar[("PD", model, segment)] = _pd_post_subjective_rag(data, models, ctx_segment, reporting_cycle, scenario)
    # Sourced from ``rows`` itself (not model_names("lgd")/("ead")) so this
    # picks up the "All Models" row those tabs' own precomputed stores carry
    # alongside their named model(s) -- see _lgd_rows / _ead_rows.
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


def _rag_heatmap_figure(rows: list[dict], theme: str, columns: list[str] = RAG_COLUMNS) -> go.Figure:
    height = heatmap_chart_height(rows)
    if not rows:
        return _empty_figure("No models are in scope for the selected filters.", height=height, theme=theme)

    y_labels = [f"{row['Model Group']} · {row['Model']}" for row in rows]
    x_labels = [column.replace(" RAG", "") for column in columns]

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
            custom_row.append([row["Model Group"], row["Model"], column.replace(" RAG", ""), display_rag(rag), row.get("Monitoring Period", ""), metric_hover])
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
        # chart (with a "?" definition chip per column), so the plot's own
        # top axis is hidden to avoid showing the same labels twice.
        xaxis=dict(side="top", showticklabels=False),
        yaxis=dict(tickfont=dict(size=12), autorange="reversed"),
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
    x_labels = [column.replace(" RAG", "") for column in columns]
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
            custom_row.append([row["Model Group"], row["Segment"], column.replace(" RAG", ""), display_rag(rag), row.get("Monitoring Period", ""), metric_hover])
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


def _build_summary_section(current_rows: list[dict], findings: list[dict], monitoring_point: str) -> html.Section:
    summary = overview_summary(current_rows)
    period_label = monitoring_point if monitoring_point and monitoring_point != "All" else "each workstream's latest period"
    assignment_breakdown = category_breakdown(findings, RAG_ASSIGNMENT_COLUMNS)
    post_subjective_breakdown = category_breakdown(findings, POST_SUBJECTIVE_COLUMNS)
    post_subjective_green = category_green_count(current_rows, POST_SUBJECTIVE_COLUMNS)

    models_by_rag = models_by_overall_rag(current_rows)

    return html.Section(
        id="overview-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.1 Overview",
                "RAG Assignment Overview",
                f"Portfolio-wide RAG posture as of {period_label}, aggregated across PD, LGD, EAD, and Loss.",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Note: "),
                    "The RAG values and Open findings above reflect each model's Overall RAG under RAG "
                    "Assignment only -- Post Subjective Review is broken out separately below.",
                ],
            ),
            html.Div(
                className="section-card overview-governance-stats",
                children=[
                    _governance_hero_stat_row(
                        "Models monitored", str(summary["models"]), "Across PD, LGD, EAD, and Loss", "blue",
                    ),
                    _final_rag_distribution_row(summary["models"]),
                ],
            ),
            html.Div(
                className="section-card overview-summary-rag-assignment",
                children=[
                    html.Span("RAG Assignment", className="overview-governance-stat-label overview-summary-rag-assignment-title"),
                    html.Div(
                        className="overview-hero-kpis overview-summary-kpis overview-summary-kpis-quad",
                        children=[
                            _hero_kpi(summary["red"], "Red", "Red", items=models_by_rag["Red"]),
                            _hero_kpi(summary["amber"], "Amber", "Amber", items=models_by_rag["Amber"]),
                            _hero_kpi(summary["green"], "Green", "Green", items=models_by_rag["Green"]),
                            _hero_kpi(
                                assignment_breakdown["breaches"],
                                "Open findings",
                                items=[
                                    (f"{assignment_breakdown['red']} Red drivers", "red"),
                                    (f"{assignment_breakdown['amber']} Amber drivers", "amber"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card overview-summary-post-subjective",
                children=[_governance_severity_stat_row("Post Subjective Review", post_subjective_breakdown, green=post_subjective_green)],
            ),
        ],
    )


def _build_segment_summary_section(current_rows: list[dict], findings: list[dict], monitoring_point: str) -> html.Section:
    """Segments-chapter equivalent of ``_build_summary_section`` -- same
    format: Segments monitored / Final RAG distribution, a RAG Assignment
    card (Red/Amber/Green/Open findings), and a Post Subjective Review bar."""
    summary = segment_overview_summary(current_rows)
    period_label = monitoring_point if monitoring_point and monitoring_point != "All" else "each segment's latest period"
    assignment_breakdown = category_breakdown(findings, RAG_ASSIGNMENT_COLUMNS)
    post_subjective_breakdown = category_breakdown(findings, POST_SUBJECTIVE_COLUMNS)
    post_subjective_green = category_green_count(current_rows, POST_SUBJECTIVE_COLUMNS)

    segments_by_rag = segments_by_overall_rag(current_rows)

    return html.Section(
        id="overview-segment-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 Overview",
                "Segment RAG Assignment Overview",
                f"Portfolio-wide RAG posture as of {period_label}, aggregated across every model group's monitored segments.",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Note: "),
                    "The RAG values and Open findings above reflect each segment's Overall RAG under RAG "
                    "Assignment only -- Post Subjective Review is broken out separately below.",
                ],
            ),
            html.Div(
                className="section-card overview-governance-stats",
                children=[
                    _governance_hero_stat_row(
                        "Segments monitored", str(summary["segments"]), "Across every model group", "blue",
                    ),
                    _final_rag_distribution_row(summary["segments"], entity_label="segment"),
                ],
            ),
            html.Div(
                className="section-card overview-summary-rag-assignment",
                children=[
                    html.Span("RAG Assignment", className="overview-governance-stat-label overview-summary-rag-assignment-title"),
                    html.Div(
                        className="overview-hero-kpis overview-summary-kpis overview-summary-kpis-quad",
                        children=[
                            _hero_kpi(summary["red"], "Red", "Red", items=segments_by_rag["Red"]),
                            _hero_kpi(summary["amber"], "Amber", "Amber", items=segments_by_rag["Amber"]),
                            _hero_kpi(summary["green"], "Green", "Green", items=segments_by_rag["Green"]),
                            _hero_kpi(
                                assignment_breakdown["breaches"],
                                "Open findings",
                                items=[
                                    (f"{assignment_breakdown['red']} Red drivers", "red"),
                                    (f"{assignment_breakdown['amber']} Amber drivers", "amber"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="section-card overview-summary-post-subjective",
                children=[_governance_severity_stat_row("Post Subjective Review", post_subjective_breakdown, green=post_subjective_green)],
            ),
        ],
    )


def _heatmap_group_headers() -> html.Div:
    """A thin banner spanning columns 1-4, 5-9, and the trailing Final RAG
    column, so the combined heatmap still visually separates RAG Assignment
    (Chapter 1) from Post Subjective Review (Chapter 2) the way the
    two-panel layout used to, plus the placeholder Final RAG verdict."""
    return html.Div(
        className="overview-heatmap-group-headers",
        children=[
            html.Div(
                "1. RAG Assignment",
                className="overview-heatmap-group-header-cell overview-heatmap-group-header-assignment",
                style={"flex": len(RAG_ASSIGNMENT_COLUMNS)},
            ),
            html.Div("2. Post Subjective Review", className="overview-heatmap-group-header-cell overview-heatmap-group-header-review", style={"flex": len(POST_SUBJECTIVE_COLUMNS)}),
            html.Div("3. Final RAG", className="overview-heatmap-group-header-cell overview-heatmap-group-header-final", style={"flex": 1}),
        ],
    )


def _heatmap_column_headers(columns: list[str]) -> html.Div:
    """Column labels with a ``?`` chip carrying each column's definition,
    replacing the RAG_COLUMN_DESCRIPTIONS text block that used to sit
    below the chart. Padding mirrors the heatmap figure's own margin
    (l=190, r=20) and gap mirrors its ``xgap`` so headers line up with
    their Plotly columns."""
    def _cell(column: str) -> html.Div:
        if column == "Overall RAG":
            return html.Div(
                className="overview-heatmap-column-header-cell overview-heatmap-column-header-overall",
                children=[
                    html.Span("Overall", className="overview-heatmap-column-header-kicker"),
                    _info_chip(RAG_COLUMN_DESCRIPTIONS[column]),
                ],
            )
        if column == FINAL_RAG_COLUMN:
            return html.Div(
                className="overview-heatmap-column-header-cell overview-heatmap-column-header-final",
                children=[
                    html.Span("Placeholder", className="overview-heatmap-column-header-kicker overview-heatmap-column-header-kicker-final"),
                    _info_chip(RAG_COLUMN_DESCRIPTIONS[column]),
                ],
            )
        return html.Div(
            className="overview-heatmap-column-header-cell",
            children=[
                html.Span(column.replace(" RAG", ""), className="overview-heatmap-column-header-title"),
                _info_chip(RAG_COLUMN_DESCRIPTIONS[column]),
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
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), all_periods)
    return _rag_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str, monitoring_point: str = "All") -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
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
                                options=_dropdown_options(RAG_COLUMNS),
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
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = periods_through(available_periods(rows), monitoring_point)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(SEGMENT_RAG_TREND_RANGE_KEY), all_periods)
    return _segment_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_segment_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str, monitoring_point: str = "All") -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
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
                                options=_dropdown_options(RAG_COLUMNS),
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
    # "All Models" (added by _pd_rows for the Model RAG Heatmap's pooled row,
    # and Loss's own sole entity) is included everywhere in the Models
    # chapter -- same pooled rollup the RAG Heatmap already shows -- so the
    # KPIs, findings, and Governance Summary all agree on one model count.
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
        options={"note": f"Reporting cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'}"},
    )
    chapter_1_sections = [
        _build_summary_section(current_rows, findings, monitoring_point or "All"),
        _build_heatmap_section(current_rows, theme, monitoring_point or "All"),
        _build_trend_section(scoped_rows, rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_governance_section(current_rows, findings),
    ]

    chapter_2 = build_pd_chapter_heading(
        "2.",
        "Segments",
        "Every model group's book of business sliced by portfolio segment instead of by model (PD pooled across "
        "both PD models).",
        options={"note": f"Reporting cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'} · Model group {segment_model_group or 'All'}"},
    )
    chapter_2_sections = [
        _build_segment_summary_section(current_segment_rows, segment_findings, monitoring_point or "All"),
        _build_segment_heatmap_section(current_segment_rows, theme, monitoring_point or "All"),
        _build_segment_trend_section(segment_scoped_rows, segment_rag_trend_metric, range_store, theme, monitoring_point or "All"),
        _build_segment_governance_section(current_segment_rows, segment_findings),
    ]

    children = [
        executive_summary,
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
                                            html.Span("1. Choose Reporting Cycle and Monitoring Point.", className="saas-getting-started-highlight"),
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
                                        html.Strong("Pick a Reporting Cycle. "),
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
                    children=html.Div(
                        id=CONTENT_ID,
                        children=build_overview_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
