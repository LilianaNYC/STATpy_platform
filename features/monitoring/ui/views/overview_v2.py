"""Layout for the Overview v2 page: a cross-portfolio RAG command center.

Combines PD, LGD, EAD, and Loss into one view built directly on each tab's
own domain functions (see ``domain/overview_v2.py``), organised as a single
chapter with five sections: RAG Assignment overview, Model RAG Heatmap,
RAG Trend Analysis, Top Findings, and Governance Summary.
"""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from .....shared.domain.calculations import filter_pd_periods_by_range
from .....shared.theme import normalize_theme_value
from .....shared.ui import controls as shared_filters
from .....shared.ui.charts import (
    _apply_transparent_background,
    _empty_figure,
    build_pd_time_series_xaxis,
)
from .....shared.ui.controls import build_chart_header
from ...domain.overview_v2 import (
    MODEL_GROUPS,
    POST_SUBJECTIVE_COLUMNS,
    RAG_ASSIGNMENT_COLUMNS,
    RAG_COLUMNS,
    RAG_COLUMN_DESCRIPTIONS,
    available_periods,
    build_overview_v2_rows,
    build_overview_v2_segment_rows,
    display_rag,
    effective_rag,
    governance_summary,
    heatmap_rows,
    overview_summary,
    resolve_current_rows,
    resolve_current_segment_rows,
    segment_governance_summary,
    segment_heatmap_rows,
    segment_overview_summary,
    segment_top_findings,
    top_findings,
)
from .cards import _info_chip, build_pd_chapter_heading, build_pd_section_heading
from .post_subjective import build_executive_summary

CONTENT_ID = "overview-v2-content"
APPLY_FILTERS_ID = "overview-v2-apply-filters"
APPLIED_FILTERS_STORE_ID = "overview-v2-applied-filters-store"
REPORTING_CYCLE_ID = "overview-v2-reporting-cycle"
REPORTING_CYCLE_TOGGLE_ID = "overview-v2-reporting-cycle-toggle"
REPORTING_CYCLE_MENU_ID = "overview-v2-reporting-cycle-menu"
REPORTING_CYCLE_FILTER_KEY = "overview-v2-reporting-cycle"
MONITORING_POINT_ID = "overview-v2-monitoring-point"
MONITORING_POINT_TOGGLE_ID = "overview-v2-monitoring-point-toggle"
MONITORING_POINT_MENU_ID = "overview-v2-monitoring-point-menu"
MONITORING_POINT_FILTER_KEY = "overview-v2-monitoring-point"
RAG_TREND_METRIC_ID = "overview-v2-rag-trend-metric"
RAG_TREND_METRIC_TOGGLE_ID = "overview-v2-rag-trend-metric-toggle"
RAG_TREND_METRIC_MENU_ID = "overview-v2-rag-trend-metric-menu"
RAG_TREND_METRIC_FILTER_KEY = "overview-v2-rag-trend-metric"
RAG_TREND_CHART_ID = "overview-v2-rag-trend-chart"
SEGMENT_RAG_TREND_METRIC_ID = "overview-v2-segment-rag-trend-metric"
SEGMENT_RAG_TREND_METRIC_TOGGLE_ID = "overview-v2-segment-rag-trend-metric-toggle"
SEGMENT_RAG_TREND_METRIC_MENU_ID = "overview-v2-segment-rag-trend-metric-menu"
SEGMENT_RAG_TREND_METRIC_FILTER_KEY = "overview-v2-segment-rag-trend-metric"
SEGMENT_RAG_TREND_CHART_ID = "overview-v2-segment-rag-trend-chart"
OVERVIEW_V2_SUBNAV_ID = "overview-v2-subnav"
RANGE_STORE_ID = "overview-v2-range-store"
SCOPED_ROWS_STORE_ID = "overview-v2-scoped-rows-store"
SEGMENT_SCOPED_ROWS_STORE_ID = "overview-v2-segment-scoped-rows-store"
RAG_TREND_RANGE_KEY = "overview_v2_rag_trend"
SEGMENT_RAG_TREND_RANGE_KEY = "overview_v2_segment_rag_trend"

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
_GROUP_ICONS = {"PD": "🧠", "LGD": "📉", "EAD": "📈", "Loss": "💰"}
_GROUP_PATHS = {"PD": "/", "LGD": "/lgd-performance", "EAD": "/ead-performance", "Loss": "/loss-performance"}


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


def _lgd_ead_post_subjective_rag(data: dict, model_type: str, sensitivity_key: str, model: str, reporting_cycle: str, scenario: str) -> dict[str, str]:
    from .post_subjective import (
        PostSubjectiveConfig, _fmt_pct, _impact_summary, _mev_range_summary, _projection_rows,
        _scenario_ranking_summary, _sensitivity_threshold, resolve_scenario_selection,
    )

    cfg = PostSubjectiveConfig(
        prefix=model_type.lower(), label=model_type, model_type=model_type,
        sensitivity_key=sensitivity_key, scenario_filter_id="overview-v2-unused",
    )
    all_rows = _projection_rows(data.get(sensitivity_key) or [], reporting_cycle, "model", model)
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
    mev_summary = _mev_range_summary(cfg, data, model, "All", reporting_cycle, scenario)
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
    from .....shared.repositories.filters_config import model_names

    scenario = _default_scenario(data)
    sidecar: dict[tuple[str, str, str], dict[str, str]] = {}

    pd_keys = {(row["Model"], row.get("Segment", "All")) for row in rows if row["Model Group"] == "PD"}
    for model, segment in pd_keys:
        # ctx uses lowercase "all" for the pooled/Segment: All case, matching
        # the PD Performance tab's own convention (see _ctx_store_keys).
        ctx_segment = "all" if segment == "All" else segment
        sidecar[("PD", model, segment)] = _pd_post_subjective_rag(data, {model}, ctx_segment, reporting_cycle, scenario)
    for model in model_names("lgd"):
        sidecar[("LGD", model, "All")] = _lgd_ead_post_subjective_rag(data, "LGD", "lgd_sensitivity_projections", model, reporting_cycle, scenario)
    for model in model_names("ead"):
        sidecar[("EAD", model, "All")] = _lgd_ead_post_subjective_rag(data, "EAD", "ead_sensitivity_projections", model, reporting_cycle, scenario)

    for row in rows:
        key = (row["Model Group"], row["Model"], row.get("Segment", "All"))
        row.update(sidecar.get(key, {}))
    return rows


def augment_segment_rows_with_post_subjective(rows: list[dict], data: dict, reporting_cycle: str) -> list[dict]:
    """Segments-chapter equivalent of ``augment_rows_with_post_subjective``:
    pools every PD model per segment (there's no single "model" to key off
    of), keyed purely by Segment."""
    scenario = _default_scenario(data)
    all_pd_models = set(data.get("model_names", []))
    sidecar: dict[str, dict[str, str]] = {}
    for segment in {row["Segment"] for row in rows}:
        sidecar[segment] = _pd_post_subjective_rag(data, all_pd_models, segment, reporting_cycle, scenario)
    for row in rows:
        row.update(sidecar.get(row["Segment"], {}))
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


def _build_overview_v2_subnav() -> html.Div:
    return html.Div(
        id=OVERVIEW_V2_SUBNAV_ID,
        className="monitoring-section-subnav",
        children=[
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("Models", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-v2-summary", "Overview", active=True),
                            _subnav_link("overview-v2-heatmap", "Model RAG Heatmap"),
                            _subnav_link("overview-v2-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-v2-top-findings", "Top Findings"),
                            _subnav_link("overview-v2-governance-summary", "Governance Summary"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="monitoring-section-subnav-group pd-subnav-group",
                children=[
                    html.Div("Segments", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-v2-segment-summary", "Overview"),
                            _subnav_link("overview-v2-segment-heatmap", "Segment RAG Heatmap"),
                            _subnav_link("overview-v2-segment-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-v2-segment-top-findings", "Top Findings"),
                            _subnav_link("overview-v2-segment-governance-summary", "Governance Summary"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _rag_badge(rag: str) -> html.Span:
    label = display_rag(rag)
    tone = "na" if rag == "N/A" else effective_rag(rag).lower()
    return html.Span(
        className=f"overview-rag-badge overview-rag-{tone}",
        title=label,
        **{"aria-label": label},
    )


def _hero_kpi(value, label: str, rag: str | None = None) -> html.Div:
    tone = effective_rag(rag).lower() if rag else "neutral"
    return html.Div(
        className=f"overview-hero-kpi overview-hero-kpi-{tone}",
        children=[
            html.Div(str(value), className="overview-hero-kpi-value"),
            html.Div(label, className="overview-hero-kpi-label"),
        ],
    )


def _insight_card(title: str, value: str, body: str, tone: str = "neutral") -> html.Div:
    return html.Div(
        className=f"overview-insight-card overview-insight-card-{tone}",
        children=[
            html.Div(title, className="overview-insight-card-kicker"),
            html.Div(value, className="overview-insight-card-value"),
            html.P(body, className="overview-insight-card-body"),
        ],
    )


def _workstream_card(group: str) -> "dcc.Link":
    return dcc.Link(
        href=_GROUP_PATHS.get(group, "/"),
        className="overview-workstream-card",
        children=[
            html.Div(f"{_GROUP_ICONS.get(group, '')} {group}", className="overview-workstream-card-kicker"),
            html.Div(f"{group} Performance", className="overview-workstream-card-title"),
            html.P(f"Open the {group} Performance tab for model-level detail and drill-down.", className="overview-workstream-card-body"),
            html.Span("Open tab", className="overview-workstream-card-cta"),
        ],
    )


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
    # Visually separate the RAG Assignment columns from the Post Subjective
    # Review columns within the single combined heatmap.
    boundary = len(RAG_ASSIGNMENT_COLUMNS) - 0.5
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
    segment instead of per model. Keeps the same margins as the model
    heatmap (rather than shrinking the left margin for shorter labels) so
    both chapters share the same ``_heatmap_panel``/column-header CSS."""
    height = heatmap_chart_height(rows)
    if not rows:
        return _empty_figure("No segments are in scope for the selected filters.", height=height, theme=theme)

    y_labels = [row["Segment"] for row in rows]
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
            custom_row.append([row["Segment"], column.replace(" RAG", ""), display_rag(rag), row.get("Monitoring Period", ""), metric_hover])
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
            "%{customdata[0]}<br>%{customdata[1]}: %{customdata[2]}"
            "%{customdata[4]}"
            "<br>As of %{customdata[3]}<extra></extra>"
        ),
    ))
    boundary = len(RAG_ASSIGNMENT_COLUMNS) - 0.5
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
    segment_keys = sorted({row["Segment"] for row in rows})
    height = _segment_trend_heatmap_height(segment_keys)
    all_periods = available_periods(rows)
    periods = [p for p in all_periods if visible_periods is None or p in set(visible_periods)]
    if not segment_keys or not periods:
        return _empty_figure("No RAG trend data is available for the selected filters.", height=height, theme=theme)

    by_key_period = {(row["Segment"], row["Monitoring Period"]): row.get(rag_column, "N/A") for row in rows}
    heatmap_z = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

    z_values, customdata = [], []
    for segment in segment_keys:
        z_row, custom_row = [], []
        for period in periods:
            rag = by_key_period.get((segment, period), "N/A")
            z_row.append(heatmap_z.get(rag, 0))
            custom_row.append([segment, display_rag(rag), period])
        z_values.append(z_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=periods,
        y=segment_keys,
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
        hovertemplate="%{customdata[0]}<br>%{customdata[2]}: %{customdata[1]}<extra></extra>",
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

    if findings:
        top_group = max(MODEL_GROUPS, key=lambda group: sum(1 for row in findings if row["Model Group"] == group), default="—")
        top_group_n = sum(1 for row in findings if row["Model Group"] == top_group)
        hotspot_body = f"{top_group_n} of {len(findings)} open findings originate from {top_group}."
        hotspot_value = top_group
        hotspot_tone = "red" if any(row["RAG"] == "Red" for row in findings if row["Model Group"] == top_group) else "amber"
    else:
        hotspot_value, hotspot_body, hotspot_tone = "None", "No Red or Amber findings across the portfolio.", "green"

    largest_group = max(MODEL_GROUPS, key=lambda group: sum(1 for row in current_rows if row["Model Group"] == group), default="—")
    largest_group_n = len({row["Model"] for row in current_rows if row["Model Group"] == largest_group})

    return html.Section(
        id="overview-v2-summary",
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
                className="section-card overview-summary-kpi-panel",
                children=[
                    html.Div(
                        className="overview-hero-kpis overview-summary-kpis",
                        children=[
                            _hero_kpi(summary["models"], "Models monitored"),
                            _hero_kpi(summary["red"], "Red", "Red"),
                            _hero_kpi(summary["amber"], "Amber", "Amber"),
                            _hero_kpi(summary["green"], "Green", "Green"),
                            _hero_kpi(len(findings), "Open findings"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="overview-insight-grid",
                children=[
                    _insight_card("Review load", f"{summary['breaches']} of {summary['models']}", "models carry a Red or Amber Overall RAG this period.", "amber" if summary["breaches"] else "green"),
                    _insight_card("Primary hotspot", hotspot_value, hotspot_body, hotspot_tone),
                    _insight_card("Largest workstream", largest_group, f"{largest_group_n} model(s) in scope.", "neutral"),
                ],
            ),
            html.Div(
                className="overview-workstream-grid",
                children=[_workstream_card(group) for group in MODEL_GROUPS],
            ),
        ],
    )


def _build_segment_summary_section(current_rows: list[dict], findings: list[dict], monitoring_point: str) -> html.Section:
    """Segments-chapter equivalent of ``_build_summary_section``. PD's
    segments have no workstream-style sub-grouping, so there's no mix chart
    or tab-link grid here -- just the hero KPIs and insight cards."""
    summary = segment_overview_summary(current_rows)
    period_label = monitoring_point if monitoring_point and monitoring_point != "All" else "each segment's latest period"

    if findings:
        metrics_present = sorted({row["Metric"] for row in findings})
        top_metric = max(metrics_present, key=lambda metric: sum(1 for row in findings if row["Metric"] == metric), default="—")
        top_metric_n = sum(1 for row in findings if row["Metric"] == top_metric)
        hotspot_value = top_metric.replace(" RAG", "")
        hotspot_body = f"{top_metric_n} of {len(findings)} open findings are {hotspot_value} breaches."
        hotspot_tone = "red" if any(row["RAG"] == "Red" for row in findings if row["Metric"] == top_metric) else "amber"

        segments_present = sorted({row["Segment"] for row in findings})
        worst_segment = max(segments_present, key=lambda segment: sum(1 for row in findings if row["Segment"] == segment), default="—")
        worst_segment_n = sum(1 for row in findings if row["Segment"] == worst_segment)
    else:
        hotspot_value, hotspot_body, hotspot_tone = "None", "No Red or Amber findings across the portfolio.", "green"
        worst_segment, worst_segment_n = "—", 0

    return html.Section(
        id="overview-v2-segment-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 Overview",
                "Segment RAG Assignment Overview",
                f"Portfolio-wide RAG posture as of {period_label}, aggregated across PD's monitored segments.",
                "Red" if summary["red"] else ("Amber" if summary["amber"] else "Green"),
                {"show_rag": False},
            ),
            html.Div(
                className="section-card overview-summary-kpi-panel",
                children=[
                    html.Div(
                        className="overview-hero-kpis overview-summary-kpis",
                        children=[
                            _hero_kpi(summary["segments"], "Segments monitored"),
                            _hero_kpi(summary["red"], "Red", "Red"),
                            _hero_kpi(summary["amber"], "Amber", "Amber"),
                            _hero_kpi(summary["green"], "Green", "Green"),
                            _hero_kpi(len(findings), "Open findings"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="overview-insight-grid",
                children=[
                    _insight_card("Review load", f"{summary['breaches']} of {summary['segments']}", "segments carry a Red or Amber Overall RAG this period.", "amber" if summary["breaches"] else "green"),
                    _insight_card("Primary hotspot", hotspot_value, hotspot_body, hotspot_tone),
                    _insight_card("Highest-risk segment", worst_segment, f"{worst_segment_n} open finding(s) in scope." if worst_segment_n else "No open findings.", "red" if worst_segment_n else "green"),
                ],
            ),
        ],
    )


def _heatmap_group_headers() -> html.Div:
    """A thin banner spanning columns 1-4 vs 5-9, so the combined heatmap
    still visually separates RAG Assignment (Chapter 1) from Post Subjective
    Review (Chapter 2) the way the two-panel layout used to."""
    return html.Div(
        className="overview-heatmap-group-headers",
        children=[
            html.Div("1. RAG Assignment", className="overview-heatmap-group-header-cell", style={"flex": len(RAG_ASSIGNMENT_COLUMNS)}),
            html.Div("2. Post Subjective Review", className="overview-heatmap-group-header-cell overview-heatmap-group-header-divider", style={"flex": len(POST_SUBJECTIVE_COLUMNS)}),
        ],
    )


def _heatmap_column_headers(columns: list[str]) -> html.Div:
    """Column labels with a ``?`` chip carrying each column's definition,
    replacing the RAG_COLUMN_DESCRIPTIONS text block that used to sit
    below the chart. Padding mirrors the heatmap figure's own margin
    (l=190, r=20) and gap mirrors its ``xgap`` so headers line up with
    their Plotly columns."""
    return html.Div(
        className="overview-heatmap-column-headers",
        children=[
            html.Div(
                className="overview-heatmap-column-header-cell",
                children=[
                    html.Span(column.replace(" RAG", "")),
                    _info_chip(RAG_COLUMN_DESCRIPTIONS[column]),
                ],
            )
            for column in columns
        ],
    )


def _rag_swatch_legend() -> html.Div:
    """Static RAG legend replacing Plotly's built-in colorbar (see the
    ``showscale=False`` note in ``_rag_heatmap_figure``) -- a fixed-width
    sidebar whose width doesn't vary with figure content, so the header
    row above the chart can predict the plot's rendered width exactly."""
    return html.Div(
        className="overview-heatmap-swatch-legend",
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
                className="overview-heatmap-graph-row",
                children=[
                    # Header rows live inside the same flex:1 column as the
                    # Graph (rather than spanning the whole card) so both
                    # measure to the identical rendered width -- the only way
                    # their fixed l/r padding reliably lines up with the
                    # chart's own l/r margin.
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
                    _rag_swatch_legend(),
                ],
            ),
        ],
    )


def _build_heatmap_section(current_rows: list[dict], theme: str) -> html.Section:
    rows = heatmap_rows(current_rows)
    return html.Section(
        id="overview-v2-heatmap",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.2 Model RAG Heatmap",
                "Cross-Model RAG Comparison",
                "Every monitored model's RAG Assignment and Post Subjective Review tests side by side, mirroring "
                "the chapter structure of each individual Performance tab.",
                "Green",
                {"show_rag": False},
            ),
            _heatmap_panel(
                rows, RAG_COLUMNS, theme,
                "Model RAG Heatmap",
                "Color always shows the RAG (RAG Assignment as of the selected Monitoring Point, Post Subjective Review as the worst case across the whole reporting cycle) with the headline metric shown underneath for Post Subjective Review cells -- hover a column header for methodology or a cell for detail, and note Loss has no post subjective review tests so those cells are always N/A.",
            ),
        ],
    )


def _build_segment_heatmap_section(current_rows: list[dict], theme: str) -> html.Section:
    rows = segment_heatmap_rows(current_rows)
    return html.Section(
        id="overview-v2-segment-heatmap",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.2 Segment RAG Heatmap",
                "Cross-Segment RAG Comparison",
                "Every monitored PD segment's RAG Assignment and Post Subjective Review tests side by side, "
                "pooled across both PD models.",
                "Green",
                {"show_rag": False},
            ),
            _heatmap_panel(
                rows, RAG_COLUMNS, theme,
                "Segment RAG Heatmap",
                "Color always shows the RAG (RAG Assignment as of the selected Monitoring Point, Post Subjective Review as the worst case across the whole reporting cycle) with the headline metric shown underneath for Post Subjective Review cells -- hover a column header for methodology or a cell for detail.",
                figure_fn=_segment_heatmap_figure,
            ),
        ],
    )


def build_trend_figure(rows: list[dict], rag_trend_metric: str, range_store: dict | None, theme: str) -> go.Figure:
    """Build the portfolio RAG trend figure. Shared by the initial section render and the
    dimension/range-driven mini-callback that updates the chart without a full re-render."""
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = available_periods(rows)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), all_periods)
    return _rag_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str) -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = available_periods(rows)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), all_periods)
    model_keys = sorted(
        {(row["Model Group"], row["Model"]) for row in rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )

    return html.Section(
        id="overview-v2-rag-trend",
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
                    html.Div(
                        className="overview-heatmap-graph-row",
                        children=[
                            dcc.Graph(
                                id=RAG_TREND_CHART_ID,
                                figure=_rag_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme),
                                config=_GRAPH_CONFIG,
                                style={"height": f"{_rag_trend_heatmap_height(model_keys)}px", "flex": "1", "minWidth": "0"},
                            ),
                            _rag_swatch_legend(),
                        ],
                    ),
                ],
            ),
        ],
    )


def build_segment_trend_figure(rows: list[dict], rag_trend_metric: str, range_store: dict | None, theme: str) -> go.Figure:
    """Segments-chapter equivalent of ``build_trend_figure``."""
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = available_periods(rows)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(SEGMENT_RAG_TREND_RANGE_KEY), all_periods)
    return _segment_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme)


def _build_segment_trend_section(rows: list[dict], rag_trend_metric: str, range_store: dict, theme: str) -> html.Section:
    rag_trend_metric = rag_trend_metric if rag_trend_metric in RAG_COLUMNS else "Overall RAG"
    all_periods = available_periods(rows)
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(SEGMENT_RAG_TREND_RANGE_KEY), all_periods)
    segment_keys = sorted({row["Segment"] for row in rows})

    return html.Section(
        id="overview-v2-segment-rag-trend",
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
                    html.Div(
                        className="overview-heatmap-graph-row",
                        children=[
                            dcc.Graph(
                                id=SEGMENT_RAG_TREND_CHART_ID,
                                figure=_segment_trend_heatmap_figure(rows, rag_trend_metric, visible_periods, theme),
                                config=_GRAPH_CONFIG,
                                style={"height": f"{_segment_trend_heatmap_height(segment_keys)}px", "flex": "1", "minWidth": "0"},
                            ),
                            _rag_swatch_legend(),
                        ],
                    ),
                ],
            ),
        ],
    )


def _findings_table(rows: list[dict], columns: list[str], empty_body: str) -> html.Div:
    if not rows:
        return html.Div(
            className="section-card pd-mev-empty-state",
            children=[
                html.Div("No open findings", className="pd-mev-chart-title"),
                html.P(empty_body),
            ],
        )
    return html.Div(
        className="overview-table-wrap overview-findings-table-wrap",
        children=[
            html.Table(
                children=[
                    html.Thead(html.Tr([html.Th(column) for column in columns])),
                    html.Tbody([
                        html.Tr([
                            html.Td([_rag_badge(row["RAG"]), html.Span(row["Current"], style={"marginLeft": "6px"})]) if column == "Current"
                            else html.Td(row[column])
                            for column in columns
                        ])
                        for row in rows
                    ]),
                ],
            ),
        ],
    )


def _build_findings_section(findings: list[dict]) -> html.Section:
    return html.Section(
        id="overview-v2-top-findings",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.4 Top Findings",
                "Red and Amber Findings",
                "Every breach across the portfolio for the selected filters, worst first.",
                "Red" if any(row["RAG"] == "Red" for row in findings) else ("Amber" if findings else "Green"),
                {"show_rag": False},
            ),
            _findings_table(
                findings,
                ["Monitoring Period", "Model Group", "Model", "Segment", "Metric", "Current"],
                "Every monitored model is Green for the selected filters.",
            ),
        ],
    )


def _build_segment_findings_section(findings: list[dict]) -> html.Section:
    return html.Section(
        id="overview-v2-segment-top-findings",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Top Findings",
                "Red and Amber Findings",
                "Every breach across PD's monitored segments for the selected filters, worst first.",
                "Red" if any(row["RAG"] == "Red" for row in findings) else ("Amber" if findings else "Green"),
                {"show_rag": False},
            ),
            _findings_table(
                findings,
                ["Monitoring Period", "Segment", "Metric", "Current"],
                "Every monitored segment is Green for the selected filters.",
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


def _governance_distribution(gov: dict, entity_label: str) -> html.Div:
    total = gov["total"]
    segments = [
        html.Span(
            className=f"overview-governance-distribution-segment overview-governance-distribution-{tone}",
            style={"width": f"{100 * gov[tone] / total:.2f}%"},
        )
        for tone in ("red", "amber", "green")
        if total and gov[tone]
    ]
    if not segments:
        segments = [html.Span(className="overview-governance-distribution-segment overview-governance-distribution-empty")]

    return html.Div(
        className="overview-governance-distribution",
        children=[
            html.Div(
                className="overview-governance-distribution-heading",
                children=[
                    html.Div(
                        children=[
                            html.Span("Overall RAG distribution"),
                            html.Strong(f"{gov['breaches']} of {total} need attention" if total else "No data in scope"),
                        ],
                    ),
                    html.Span(f"{total} {entity_label}{'' if total == 1 else 's'}", className="overview-governance-total"),
                ],
            ),
            html.Div(
                segments,
                className="overview-governance-distribution-bar",
                role="img",
                **{
                    "aria-label": (
                        f"Overall RAG distribution: {gov['red']} Red, {gov['amber']} Amber, "
                        f"{gov['green']} Green."
                    )
                },
            ),
            html.Div(
                className="overview-governance-distribution-legend",
                children=[
                    html.Span([html.I(className=f"overview-governance-dot overview-governance-dot-{tone}"), f"{label} {gov[tone]}"])
                    for tone, label in (("red", "Red"), ("amber", "Amber"), ("green", "Green"))
                ],
            ),
        ],
    )


def _governance_fact(value, label: str, description: str, tone: str) -> html.Div:
    value_text = str(value)
    value_class = "overview-governance-fact-value"
    if len(value_text) > 5:
        value_class += " overview-governance-fact-value-text"
    return html.Div(
        className=f"overview-governance-fact overview-governance-fact-{tone}",
        children=[
            html.Span(label, className="overview-governance-fact-label"),
            html.Strong(value_text, className=value_class),
            html.Span(description, className="overview-governance-fact-description"),
        ],
    )


def _governance_action_register(gov: dict, entity_label: str) -> html.Div:
    rows = gov["escalations"]
    plural = entity_label if len(rows) == 1 else f"{entity_label}s"
    action_rows = []
    for row in rows:
        if entity_label == "model":
            entity_name = row["Model"]
            entity_context = row["Model Group"]
        else:
            entity_name = row["Segment"]
            entity_context = "PD segment"
        drivers = [driver.strip() for driver in row["Drivers"].split(",") if driver.strip()]
        action_rows.append(
            html.Div(
                className="overview-governance-action-row",
                children=[
                    html.Div(
                        className="overview-governance-action-entity",
                        children=[
                            html.Span("Red", className="overview-governance-action-rag"),
                            html.Div(
                                children=[
                                    html.Strong(entity_name),
                                    html.Span(f"{entity_context} · As of {row['Monitoring Period']}"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-governance-action-drivers",
                        children=[
                            html.Span("Drivers", className="overview-governance-action-driver-label"),
                            html.Div(
                                [html.Span(driver, className="overview-governance-driver-chip") for driver in drivers],
                                className="overview-governance-driver-list",
                            ),
                        ],
                    ),
                ],
            )
        )

    if not action_rows:
        action_rows = [
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
                className="overview-governance-actions-heading",
                children=[
                    html.Div(
                        children=[
                            html.Span("Required action"),
                            html.Strong("Escalation register"),
                        ],
                    ),
                    html.Span(
                        f"{len(rows)} {plural}",
                        className=f"overview-governance-actions-count {'is-clear' if not rows else ''}",
                    ),
                ],
            ),
            html.Div(action_rows, className="overview-governance-action-list"),
        ],
    )


def _governance_board(gov: dict, entity_label: str, clean_key: str, clean_label: str) -> html.Div:
    posture_title, posture_detail, tone = _governance_posture(gov, entity_label)
    clean_entities = gov[clean_key]
    clean_description = ", ".join(clean_entities) if clean_entities else "None fully clear"
    top_metric = gov["top_metric"] if gov["top_metric"] != "None" else "No findings"
    driver_count = gov["top_metric_count"]

    return html.Div(
        className=f"section-card overview-governance-board overview-governance-board-{tone}",
        children=[
            html.Div(
                className="overview-governance-board-top",
                children=[
                    html.Div(
                        className="overview-governance-posture",
                        children=[
                            html.Div(
                                className="overview-governance-posture-heading",
                                children=[
                                    html.Div(
                                        children=[
                                            html.Span("Current governance posture"),
                                            html.H4(posture_title),
                                        ],
                                    ),
                                    html.Span(posture_detail, className=f"overview-governance-posture-pill is-{tone}"),
                                ],
                            ),
                            html.P(gov["narrative"]),
                        ],
                    ),
                    _governance_distribution(gov, entity_label),
                ],
            ),
            html.Div(
                className="overview-governance-facts",
                children=[
                    _governance_fact(
                        len(gov["escalations"]),
                        "Immediate escalation",
                        "Red on any test",
                        "red" if gov["escalations"] else "green",
                    ),
                    _governance_fact(
                        gov["breaches"],
                        "Review queue",
                        "Red or Amber Overall RAG",
                        "amber" if gov["breaches"] else "green",
                    ),
                    _governance_fact(
                        top_metric,
                        "Leading driver",
                        f"{driver_count} open finding{'' if driver_count == 1 else 's'}",
                        "blue" if driver_count else "green",
                    ),
                    _governance_fact(
                        len(clean_entities),
                        clean_label,
                        clean_description,
                        "green",
                    ),
                ],
            ),
            _governance_action_register(gov, entity_label),
        ],
    )


def _build_governance_section(current_rows: list[dict], findings: list[dict]) -> html.Section:
    gov = governance_summary(current_rows, findings)
    return html.Section(
        id="overview-v2-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "1.5 Governance Summary",
                "Decision Summary",
                "A concise governance posture, the signals driving it, and the actions requiring attention.",
                "Green",
                {"show_rag": False},
            ),
            _governance_board(gov, "model", "clean_groups", "Clear workstreams"),
        ],
    )


def _build_segment_governance_section(current_rows: list[dict], findings: list[dict]) -> html.Section:
    gov = segment_governance_summary(current_rows, findings)
    return html.Section(
        id="overview-v2-segment-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.5 Governance Summary",
                "Decision Summary",
                "A concise segment-level posture, the signals driving it, and the actions requiring attention.",
                "Green",
                {"show_rag": False},
            ),
            _governance_board(gov, "segment", "clean_segments", "Clear segments"),
        ],
    )


# ---------------------------------------------------------------------------
# Content renderer
# ---------------------------------------------------------------------------


def render_overview_v2_content(
    data: dict,
    reporting_cycle: str,
    monitoring_point: str,
    rag_trend_metric: str,
    segment_rag_trend_metric: str,
    range_store: dict | None,
    theme_value: str | None = None,
) -> tuple[list, list[dict], list[dict]]:
    """Returns ``(content_children, scoped_rows, segment_scoped_rows)``, cached into
    ``SCOPED_ROWS_STORE_ID`` / ``SEGMENT_SCOPED_ROWS_STORE_ID`` so each chapter's RAG-trend
    dimension/range controls can update just that chart without recomputing the whole page
    (see ``build_trend_figure`` / ``build_segment_trend_figure``)."""
    theme = normalize_theme_value(theme_value)
    range_store = range_store or {}

    scoped_rows = build_overview_v2_rows(data, reporting_cycle)
    segment_scoped_rows = build_overview_v2_segment_rows(data, reporting_cycle)
    # Post Subjective Review is cycle-level (same verdict on every quarter row
    # for an entity, per augment_rows_with_post_subjective's own docstring), so
    # this must run on every quarter in scoped_rows -- not just the resolved
    # "current" row -- otherwise the RAG Trend heatmaps see those columns as
    # unset (N/A) everywhere except whichever quarter happens to be current.
    scoped_rows = augment_rows_with_post_subjective(scoped_rows, data, reporting_cycle)
    segment_scoped_rows = augment_segment_rows_with_post_subjective(segment_scoped_rows, data, reporting_cycle)
    current_rows = resolve_current_rows(scoped_rows, monitoring_point or "All")
    current_segment_rows = resolve_current_segment_rows(segment_scoped_rows, monitoring_point or "All")
    findings = top_findings(current_rows)
    segment_findings = segment_top_findings(current_segment_rows)

    executive_summary = build_executive_summary(
        "Overview v2 is the cross-portfolio command center for PD, LGD, EAD, and Loss model monitoring. It "
        "reuses each tab's own RAG logic — nothing is re-derived — so the picture here always agrees with what "
        "each individual Performance tab shows, rolled up into a Models chapter and a Segments chapter, each "
        "with its own RAG heatmap, trend, and governance-ready findings summary.",
        theme,
    )

    chapter_1 = build_pd_chapter_heading(
        "1.",
        "Models",
        "Cross-portfolio monitoring view combining PD, LGD, EAD, and Loss models into a single RAG posture.",
        options={"note": f"Reporting cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'}"},
    )
    chapter_1_sections = [
        _build_summary_section(current_rows, findings, monitoring_point or "All"),
        _build_heatmap_section(current_rows, theme),
        _build_trend_section(scoped_rows, rag_trend_metric, range_store, theme),
        _build_findings_section(findings),
        _build_governance_section(current_rows, findings),
    ]

    chapter_2 = build_pd_chapter_heading(
        "2.",
        "Segments",
        "PD's book of business sliced by portfolio segment instead of by model, pooled across both PD models.",
        options={"note": f"Reporting cycle {reporting_cycle} · Monitoring point {monitoring_point or 'All'}"},
    )
    chapter_2_sections = [
        _build_segment_summary_section(current_segment_rows, segment_findings, monitoring_point or "All"),
        _build_segment_heatmap_section(current_segment_rows, theme),
        _build_segment_trend_section(segment_scoped_rows, segment_rag_trend_metric, range_store, theme),
        _build_segment_findings_section(segment_findings),
        _build_segment_governance_section(current_segment_rows, segment_findings),
    ]

    children = [
        executive_summary,
        chapter_1,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=chapter_1_sections),
        chapter_2,
        html.Div(className="pd-chapter-body pd-chapter-body-primary", children=chapter_2_sections),
    ]
    return children, scoped_rows, segment_scoped_rows


def _build_overview_v2_apply_button() -> html.Div:
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


def build_overview_v2_apply_prompt() -> html.Section:
    return html.Section(
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    "Overview v2 is the cross-portfolio command center for PD, LGD, EAD, and Loss model "
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
                            html.Div("Getting started with Overview v2", className="pd-mev-chart-title"),
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
                                        "same five sub-sections:",
                                        html.Ul(
                                            className="saas-getting-started-substeps",
                                            children=[
                                                html.Li([html.Strong("1. Models — "), "PD, LGD, EAD, and Loss, one row per model. Overview, Model RAG Heatmap, RAG Trend Analysis, Top Findings, and Governance Summary."]),
                                                html.Li([html.Strong("2. Segments — "), "PD's book of business pooled across both PD models, one row per portfolio segment. The same five sub-sections, sliced by segment instead of model."]),
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
    """Build the Overview v2 page with top controls and the Apply-gated landing content."""
    from .....shared.repositories.filters_config import load_filter_config
    cfg = load_filter_config()
    reporting_cycle_options = [{"label": c["label"], "value": c["value"]} for c in cfg["reporting_cycles"]]
    default_cycle = reporting_cycle_options[0]["value"] if reporting_cycle_options else "CCAR 2026"
    cycle_quarters = shared_filters.REPORTING_CYCLE_QUARTERS.get(default_cycle, [])
    monitoring_point_options = [{"label": q, "value": q} for q in cycle_quarters]
    default_monitoring_point = cycle_quarters[0] if cycle_quarters else ""

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
                                _build_overview_v2_apply_button(),
                            ],
                        ),
                        html.Div(style={"marginTop": "12px"}, children=[_build_overview_v2_subnav()]),
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
                        children=build_overview_v2_apply_prompt(),
                    ),
                ),
            ],
        ),
    ]
