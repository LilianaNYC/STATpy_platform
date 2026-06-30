"""General monitoring overview page for the dashboard.

Ported from ``integrated:pages/monitoring_overview_layout.py`` into the
main-branch page structure.
"""

from __future__ import annotations

from collections import Counter

import plotly.graph_objects as go
from dash import dcc, html

from .....shared.ui.charts import (
    build_pd_time_series_xaxis,
    _rag_score_band_shapes,
    _rag_score_yaxis,
    _vertical_marker,
    _apply_transparent_background,
)
from .....shared.domain.constants import pd_rag_color
from .....shared.ui import controls as shared_filters
from .....shared.ui.controls import build_range_controls
from .....shared.domain.calculations import filter_pd_periods_by_range, pd_tone_class
from ...domain.overview import (
    RAG_COLUMNS,
    RAG_SCORE,
    build_overview_rows,
    display_rag,
    effective_rag,
    filter_overview_rows,
    heatmap_rows,
    overview_filter_options,
    overview_summary,
    top_findings,
)

CONTENT_ID = "overview-content"
PERIOD_ID = "overview-monitoring-period"
MODEL_GROUP_ID = "overview-model-group"
MODEL_ID = "overview-model"
SEGMENT_ID = "overview-segment"
PERIOD_TOGGLE_ID = "overview-monitoring-period-toggle"
PERIOD_MENU_ID = "overview-monitoring-period-menu"
MODEL_GROUP_TOGGLE_ID = "overview-model-group-toggle"
MODEL_GROUP_MENU_ID = "overview-model-group-menu"
MODEL_TOGGLE_ID = "overview-model-toggle"
MODEL_MENU_ID = "overview-model-menu"
MODEL_SELECT_ALL_ID = "overview-model-select-all"
SEGMENT_TOGGLE_ID = "overview-segment-toggle"
SEGMENT_MENU_ID = "overview-segment-menu"
PERIOD_FILTER_KEY = "overview-monitoring-period"
MODEL_GROUP_FILTER_KEY = "overview-model-group"
MODEL_FILTER_KEY = "overview-model"
SEGMENT_FILTER_KEY = "overview-segment"
RAG_TREND_METRIC_ID = "overview-rag-trend-metric"
OVERVIEW_SUBNAV_ID = "overview-subnav"
RANGE_STORE_ID = "overview-range-store"
RAG_TREND_RANGE_KEY = "overview_rag_trend"

RAG_LABELS = {
    "Overall RAG": "Model RAG (Post Subjective Review)",
}
HEATMAP_LABELS = {
    "Calibration Conservatism RAG": "Calibration",
    "Discriminatory Power RAG": "Discrimination",
    "Performance RAG": "Performance",
    "Overall RAG": "Model RAG",
    "Pre-Mitigation RAG": "Pre-Mitigation",
    "Post-Mitigation RAG": "Post-Mitigation",
}
RAG_TREND_OPTIONS = list(RAG_COLUMNS)
_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
RAG_DESCRIPTIONS = {
    "Calibration Conservatism RAG": "The objective is to assess the magintude and direction of prediction error to conclude on the level of conservatism.",
    "Discriminatory Power RAG": "Tests whether the model estimates are rank ordering the counter parties by the actual risk observed.",
    "Performance RAG": "Also called Model RAG (initial), it is based on the results of tests applied at the modelled outcomes.",
    "Overall RAG": "Reflects the impact of any subjective overlay with appropiate justification.",
    "Pre-Mitigation RAG": "Obtained from a trend of Model RAG (post subjective review) from the current and past monitoring outcomes. For ST models, only the current one will be considered.",
    "Post-Mitigation RAG": "Based on the residual risk of the model. The residual risk is judgement based and includes manual overlays, compensating controls, etc.",
}
RAG_MARKER_COLORS = {
    "Green": "#16a34a",
    "Amber": "#d97706",
    "Red": "#dc2626",
    "N/A": "#94a3b8",
}
MONITORING_WORKSTREAMS = (
    {
        "path": "/overview",
        "label": "Overview",
        "eyebrow": "Portfolio Pulse",
        "description": "Cross-model RAG comparison, trend context, and governance-ready findings.",
    },
    {
        "path": "/",
        "label": "PD Performance",
        "eyebrow": "Core Monitoring",
        "description": "Calibration, discrimination, rank ordering, and MEV range diagnostics.",
    },
    {
        "path": "/lgd-performance",
        "label": "LGD Performance",
        "eyebrow": "Recovery Lens",
        "description": "Loss-given-default overview flow and recovery behavior checkpoints.",
    },
    {
        "path": "/ead-performance",
        "label": "EAD Performance",
        "eyebrow": "Exposure Lens",
        "description": "Exposure-at-default monitoring with utilization and conversion coverage.",
    },
    {
        "path": "/loss-performance",
        "label": "Loss Performance",
        "eyebrow": "Loss Lens",
        "description": "Portfolio loss flow, realized loss signals, and performance summary.",
    },
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rag_label(column: str) -> str:
    return RAG_LABELS.get(column, column)


def _dropdown_options(values: list[str], labels: dict[str, str] | None = None) -> list[dict]:
    labels = labels or {}
    return [{"label": labels.get(value, value), "value": value} for value in values]


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
                className="monitoring-section-subnav-group pd-subnav-group active",
                children=[
                    html.Div("RAG Assignment", className="monitoring-section-subnav-label"),
                    html.Div(
                        className="monitoring-section-subnav-links",
                        children=[
                            _subnav_link("overview-summary", "Overview", active=True),
                            _subnav_link("overview-heatmap", "Model RAG Heatmap"),
                            _subnav_link("overview-rag-trend", "RAG Trend Analysis"),
                            _subnav_link("overview-top-findings", "Top Findings"),
                            _subnav_link("overview-governance-summary", "Governance Summary"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _rag_visual_tone(rag: str | None) -> str:
    if rag == "Neutral":
        return "neutral"
    return "fallback" if rag == "N/A" else pd_tone_class(effective_rag(rag))


def _rag_marker_color(rag: str | None) -> str:
    return RAG_MARKER_COLORS["N/A"] if rag == "N/A" else RAG_MARKER_COLORS.get(effective_rag(rag), "#94a3b8")


def _rag_badge(rag: str) -> html.Span:
    label = "No findings" if rag == "Neutral" else display_rag(rag)
    return html.Span(
        className=f"overview-rag-badge overview-rag-{_rag_visual_tone(rag)}",
        title=label,
        **{"aria-label": label},
    )


def _rag_legend_item(rag: str, label: str, description: str) -> html.Div:
    return html.Div(
        className="overview-rag-legend-item",
        children=[
            _rag_badge(rag),
            html.Div(
                children=[
                    html.Strong(label),
                    html.Span(description),
                ]
            ),
        ],
    )


def _rag_heatmap_legend() -> html.Div:
    return html.Div(
        className="overview-rag-legend",
        children=[
            _rag_legend_item("Green", "Green", "In tolerance."),
            _rag_legend_item("Amber", "Amber", "Review signal."),
            _rag_legend_item("Red", "Red", "Finding / breach."),
            _rag_legend_item("N/A", "Fallback Amber", "No modeled RAG available; counted and trended as Amber."),
        ],
    )


def _rag_header(column: str) -> html.Th:
    if column not in RAG_COLUMNS:
        return html.Th(column)
    description = RAG_DESCRIPTIONS[column]
    return html.Th(
        html.Span(
            className="overview-rag-header",
            children=[
                html.Span(HEATMAP_LABELS[column], title=_rag_label(column)),
                html.Span(
                    "?",
                    className="pd-info-chip",
                    role="img",
                    **{"aria-label": description, "title": description},
                ),
            ],
        )
    )


def _hero_kpi(value: int | str, label: str, rag: str | None = None) -> html.Div:
    tone = pd_tone_class(rag) if rag else "neutral"
    return html.Div(
        className=f"overview-hero-kpi overview-hero-kpi-{tone}",
        children=[
            html.Div(str(value), className="overview-hero-kpi-value"),
            html.Div(label, className="overview-hero-kpi-label"),
        ],
    )


def _scope_chip(label: str, value: str) -> html.Div:
    return html.Div(
        className="overview-scope-chip",
        children=[
            html.Span(label, className="overview-scope-chip-label"),
            html.Strong(value),
        ],
    )


def _review_queue_row(rag: str, value: int, label: str, description: str) -> html.Div:
    tone = pd_tone_class(rag)
    return html.Div(
        className=f"overview-review-row overview-review-row-{tone}",
        children=[
            html.Div(
                className="overview-review-row-main",
                children=[
                    _rag_badge(rag),
                    html.Div(
                        children=[
                            html.Strong(label),
                            html.Span(description),
                        ],
                    ),
                ],
            ),
            html.Div(str(value), className="overview-review-row-value"),
        ],
    )


def _rag_mix_bar(summary: dict) -> html.Div:
    segments = []
    for rag, key, label in (("Red", "red", "Red"), ("Amber", "amber", "Amber"), ("Green", "green", "Green")):
        value = summary[key]
        if value:
            segments.append(
                html.Span(
                    className=f"overview-rag-mix-segment overview-rag-mix-{pd_tone_class(rag)}",
                    style={"flex": str(value)},
                    title=f"{label}: {value} model(s)",
                    **{"aria-label": f"{label}: {value} model(s)"},
                )
            )

    if not segments:
        segments = [html.Span(className="overview-rag-mix-segment overview-rag-mix-empty")]

    return html.Div(className="overview-rag-mix-bar", children=segments)


def _insight_card(title: str, value: str, body: str, tone: str = "neutral") -> html.Div:
    return html.Div(
        className=f"overview-insight-card overview-insight-card-{tone}",
        children=[
            html.Div(title, className="overview-insight-card-kicker"),
            html.Div(value, className="overview-insight-card-value"),
            html.P(body, className="overview-insight-card-body"),
        ],
    )


def _workstream_card(path: str, eyebrow: str, label: str, description: str, *, active: bool = False):
    return dcc.Link(
        href=path,
        className=f"overview-workstream-card{' active' if active else ''}",
        children=[
            html.Div(eyebrow, className="overview-workstream-card-kicker"),
            html.Div(label, className="overview-workstream-card-title"),
            html.P(description, className="overview-workstream-card-body"),
            html.Span("Open tab", className="overview-workstream-card-cta"),
        ],
    )


def _scope_value(selection: str | list[str], all_label: str, current_label: str | None = None) -> str:
    if isinstance(selection, list):
        if not selection:
            return "No models selected"
        if len(selection) == 1:
            return selection[0]
        return f"{len(selection)} models selected"
    if selection == "All":
        return current_label or all_label
    return selection


def _leading_metric(findings: list[dict]) -> tuple[str, int]:
    metric_counts = Counter(_rag_label(row["Metric"]) for row in findings)
    return metric_counts.most_common(1)[0] if metric_counts else ("No active findings", 0)


def _risk_group(findings: list[dict], heat_rows: list[dict]) -> tuple[str, int]:
    finding_counts = Counter(row["Model Group"] for row in findings)
    if finding_counts:
        return finding_counts.most_common(1)[0]

    model_counts = Counter(row["Model Group"] for row in heat_rows)
    return model_counts.most_common(1)[0] if model_counts else ("No grouped models", 0)


def _heatmap_rag_counts(rows: list[dict]) -> Counter:
    return Counter(row[column] for row in rows for column in RAG_COLUMNS)


def _heatmap_stat(rag: str, label: str, value: int) -> html.Div:
    return html.Div(
        className=f"overview-heatmap-stat overview-heatmap-stat-{_rag_visual_tone(rag)}",
        children=[
            html.Div(
                className="overview-heatmap-stat-label",
                children=[_rag_badge(rag), html.Span(label)],
            ),
            html.Strong(str(value)),
        ],
    )


def _rag_heatmap_cell(column: str, rag: str) -> html.Div:
    label = display_rag(rag)
    return html.Div(
        className=f"overview-heatmap-cell overview-heatmap-cell-{_rag_visual_tone(rag)}",
        title=f"{_rag_label(column)}: {label}",
        **{"aria-label": f"{_rag_label(column)}: {label}"},
        children=[
            _rag_badge(rag),
            html.Span(label),
        ],
    )


def _rag_heatmap_table(rows: list[dict]) -> html.Div:
    columns = ["Model Group", "Model", *RAG_COLUMNS]
    counts = _heatmap_rag_counts(rows)
    return html.Div(
        className="overview-heatmap-panel",
        children=[
            html.Div(
                className="overview-heatmap-summary",
                children=[
                    html.Div(
                        className="overview-heatmap-summary-copy",
                        children=[
                            html.Div("Heatmap status", className="overview-heatmap-summary-kicker"),
                            html.H4("RAG cells by status"),
                            html.P("Use the matrix below to scan which model and dimension is driving the review queue."),
                        ],
                    ),
                    html.Div(
                        className="overview-heatmap-stat-grid",
                        children=[
                            _heatmap_stat("Red", "Red", counts.get("Red", 0)),
                            _heatmap_stat("Amber", "Amber", counts.get("Amber", 0)),
                            _heatmap_stat("N/A", "Fallback Amber", counts.get("N/A", 0)),
                            _heatmap_stat("Green", "Green", counts.get("Green", 0)),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="overview-table-wrap overview-heatmap-table-wrap",
                children=[
                    html.Table(
                        className="overview-heatmap-table",
                        children=[
                            html.Thead(html.Tr([_rag_header(column) for column in columns])),
                            html.Tbody(
                                [
                                    html.Tr(
                                        [
                                            html.Td(row["Model Group"], className="overview-heatmap-model-group"),
                                            html.Td(row["Model"], className="overview-heatmap-model-name"),
                                            *[
                                                html.Td(
                                                    _rag_heatmap_cell(column, row[column]),
                                                    className="overview-heatmap-rag-td",
                                                )
                                                for column in RAG_COLUMNS
                                            ],
                                        ]
                                    )
                                    for row in rows
                                ]
                            ),
                        ],
                    ),
                ],
            ),
            _rag_heatmap_legend(),
        ],
    )


def _findings_table(rows: list[dict]) -> html.Div:
    columns = ["Monitoring Period", "Model Group", "Model", "Metric", "Current", "Threshold"]
    if not rows:
        rows = [{
            "Monitoring Period": "-",
            "Model Group": "All",
            "Model": "No heatmap findings",
            "Metric": "-",
            "Current": "-",
            "Threshold": "-",
            "RAG": "Green",
        }]
    return html.Div(
        className="overview-table-wrap overview-findings-table-wrap",
        children=[
            html.Table(
                children=[
                    html.Thead(html.Tr([html.Th(column) for column in columns])),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(_rag_badge(row["RAG"]))
                                    if column == "Current" and row["RAG"] != "Green"
                                    else html.Td(_rag_label(row[column]) if column == "Metric" else row[column])
                                    for column in columns
                                ]
                            )
                            for row in rows
                        ]
                    ),
                ]
            )
        ],
    )


def _worst_period_rag(rows: list[dict], rag_column: str) -> str:
    return max(
        (row.get(rag_column, "N/A") for row in rows),
        key=lambda rag: (RAG_SCORE.get(effective_rag(rag), 0), 0 if rag == "N/A" else 1),
        default="N/A",
    )


_PD_RAG_SCORE = {"Red": 1, "Amber": 2, "Green": 3}


def _rag_trend_figure(rows: list[dict], rag_column: str, model_group: str, model_name: str, visible_periods: list[str]) -> go.Figure:
    model_rows = [row for row in rows if row["Model Group"] == model_group and row["Model"] == model_name]
    model_periods = {row["Monitoring Period"] for row in model_rows}
    periods = [period for period in visible_periods if period in model_periods]
    rags = [_worst_period_rag([row for row in model_rows if row["Monitoring Period"] == period], rag_column) for period in periods]
    rag_scores = [_PD_RAG_SCORE.get(effective_rag(rag)) for rag in rags]

    shapes = _rag_score_band_shapes()
    if periods:
        shapes.append(_vertical_marker(periods[-1]))

    fig = go.Figure(go.Scatter(
        x=periods,
        y=rag_scores,
        mode="markers",
        name="RAG",
        marker=dict(color=[pd_rag_color(effective_rag(rag)) for rag in rags], size=16, opacity=0.95, line=dict(color="#ffffff", width=1)),
        customdata=[display_rag(rag) for rag in rags],
        hovertemplate="%{x}<br>RAG: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=290,
        margin=dict(t=18, r=28, b=54, l=78),
        hovermode="closest",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(periods, {"title": "Monitoring Point", "gridcolor": "#e5e7eb"}, density="tight"),
        yaxis=_rag_score_yaxis(_rag_label(rag_column)),
    )
    _apply_transparent_background(fig)
    return fig


def _rag_trend_graphs(rows: list[dict], rag_column: str, range_store: dict | None = None) -> html.Div:
    model_keys = sorted({(row["Model Group"], row["Model"]) for row in rows})
    trend_periods = sorted({row["Monitoring Period"] for row in rows})
    visible_periods = filter_pd_periods_by_range((range_store or {}).get(RAG_TREND_RANGE_KEY), trend_periods)
    return html.Div(
        className="overview-trend-grid",
        children=[
            html.Div(
                className="section-card pd-default-rate-trend-section",
                children=[
                    html.Div(
                        className="pd-chart-heading",
                        children=html.Div(
                            className="pd-chart-heading-copy",
                            children=[
                                html.Div(f"{model_group}: {model_name}", className="section-title"),
                                html.Div(f"{_rag_label(rag_column)} trend across monitoring points.", className="pd-section-subtitle"),
                            ],
                        ),
                    ),
                    dcc.Graph(
                        figure=_rag_trend_figure(rows, rag_column, model_group, model_name, visible_periods),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium",
                    ),
                ],
            )
            for model_group, model_name in model_keys
        ],
    )


def _findings_summary_rag(findings: list[dict]) -> str:
    if any(effective_rag(row["RAG"]) == "Red" for row in findings):
        return "Red"
    if any(effective_rag(row["RAG"]) == "Amber" for row in findings):
        return "Amber"
    return "N/A"


# ---------------------------------------------------------------------------
# Content rendering
# ---------------------------------------------------------------------------


def render_overview_content(
    data: dict,
    overview_rows: list[dict],
    monitoring_period: str = "All",
    model_group: str = "All",
    model: str = "All",
    segment: str = "All",
    rag_trend_metric: str = "Overall RAG",
    range_store: dict | None = None,
) -> list:
    rows = filter_overview_rows(overview_rows, monitoring_period, model_group, model, segment)
    if not rows:
        return [html.Div("No overview data is available for the selected filters.", className="section-card")]

    summary = overview_summary(rows, monitoring_period)
    heat_rows = heatmap_rows(rows, monitoring_period)
    latest_period = monitoring_period if monitoring_period != "All" else max(row["Monitoring Period"] for row in rows)
    findings = top_findings(heat_rows)
    red_findings = sum(1 for row in findings if effective_rag(row["RAG"]) == "Red")
    amber_findings = sum(1 for row in findings if effective_rag(row["RAG"]) == "Amber")
    findings_rag = _findings_summary_rag(findings)
    trend_periods = sorted({row["Monitoring Period"] for row in rows})
    range_store = range_store or {}
    leading_metric, leading_metric_count = _leading_metric(findings)
    risk_group, _ = _risk_group(findings, heat_rows)
    model_group_counts = Counter(row["Model Group"] for row in heat_rows)
    largest_workstream, largest_workstream_count = (
        model_group_counts.most_common(1)[0] if model_group_counts else ("No workstreams", 0)
    )

    breaches = summary["red"] + summary["amber"]
    selected_period = _scope_value(monitoring_period, "Latest available", latest_period)
    selected_group = _scope_value(model_group, "All monitoring workstreams")
    selected_segment = _scope_value(segment, "All segments")
    selected_model = _scope_value(model, "All models in scope")

    summary_section = html.Section(
        id="overview-summary",
        className="pd-content-section pd-overview-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("Monitoring Status", className="pd-content-kicker"),
                    html.H3("Model Monitoring Summary"),
                    html.P(f"At-a-glance view of all monitored models for {latest_period}."),
                ],
            ),
            html.Div(
                className="overview-command-grid",
                children=[
                    html.Div(
                        className="overview-command-hero",
                        children=[
                            html.Div(
                                className="overview-command-hero-copy",
                                children=[
                                    html.Div("Monitoring command center", className="overview-command-hero-kicker"),
                                    html.H4("Current RAG posture across the Monitoring workstreams."),
                                    html.P(
                                        "The summary keeps the current filter scope visible, separates Red and Amber pressure, "
                                        "and preserves a path into the detailed workstream tabs."
                                    ),
                                ],
                            ),
                            html.Div(
                                className="overview-scope-chip-row",
                                children=[
                                    _scope_chip("Monitoring point", selected_period),
                                    _scope_chip("Workstream", selected_group),
                                    _scope_chip("Segment", selected_segment),
                                    _scope_chip("Model", selected_model),
                                ],
                            ),
                            html.Div(
                                className="overview-hero-kpis",
                                children=[
                                    _hero_kpi(summary["models"], "Models Monitored"),
                                    _hero_kpi(summary["red"], "Red", "Red"),
                                    _hero_kpi(summary["amber"], "Amber", "Amber"),
                                    _hero_kpi(summary["green"], "Green", "Green"),
                                    _hero_kpi(len(findings), "Findings", findings_rag if findings else None),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-review-card",
                        children=[
                            html.Div(
                                className="overview-review-card-heading",
                                children=[
                                    html.Div("Review queue", className="overview-review-card-kicker"),
                                    html.H4("What needs attention"),
                                    html.P("Counts reflect the current filter scope and the latest selected monitoring point."),
                                ],
                            ),
                            html.Div(
                                className="overview-review-card-body",
                                children=[
                                    html.Div(
                                        className="overview-rag-mix",
                                        children=[
                                            html.Div(
                                                className="overview-rag-mix-heading",
                                                children=[
                                                    html.Span("RAG assignment mix"),
                                                    html.Strong(f"{summary['models']} model(s)"),
                                                ],
                                            ),
                                            _rag_mix_bar(summary),
                                        ],
                                    ),
                                    _review_queue_row("Red", summary["red"], "Escalate", "Models with Red overall RAG."),
                                    _review_queue_row("Amber", summary["amber"], "Review", "Models with Amber overall RAG."),
                                    _review_queue_row("Green", summary["green"], "In tolerance", "Models without active RAG pressure."),
                                    html.Div(
                                        className="overview-review-focus",
                                        children=[
                                            html.Div(
                                                children=[
                                                    html.Span("Priority dimension"),
                                                    html.Strong(leading_metric),
                                                ],
                                            ),
                                            html.Div(
                                                children=[
                                                    html.Span("Workstream pressure"),
                                                    html.Strong(risk_group),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="overview-insight-grid",
                children=[
                    _insight_card(
                        "Review load",
                        str(breaches),
                        (
                            "No monitored models are currently in Amber or Red."
                            if breaches == 0
                            else f"{breaches} model(s) currently need review attention across the selected scope."
                        ),
                        "green" if breaches == 0 else "red" if summary["red"] else "amber",
                    ),
                    _insight_card(
                        "Primary hotspot",
                        leading_metric,
                        (
                            "No active findings are present in the current selection."
                            if leading_metric_count == 0
                            else f"{leading_metric_count} finding(s) are concentrated in this RAG dimension."
                        ),
                        "blue" if leading_metric_count == 0 else "amber",
                    ),
                    _insight_card(
                        "Largest workstream",
                        largest_workstream,
                        (
                            "No workstream counts are available for the current selection."
                            if largest_workstream_count == 0
                            else f"{largest_workstream_count} model(s) are in scope here, with the most pressure currently in {risk_group}."
                        ),
                        "blue",
                    ),
                ],
            ),
            html.Div(
                className="section-card overview-workstream-panel",
                children=[
                    html.Div(
                        className="overview-workstream-panel-heading",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("Monitoring tabs", className="pd-content-kicker"),
                                    html.H4("Move from summary to detailed analysis"),
                                    html.P(
                                        "Overview should help you decide where to go next. These links mirror the Monitoring workstreams in the sidebar."
                                    ),
                                ]
                            ),
                        ],
                    ),
                    html.Div(
                        className="overview-workstream-grid",
                        children=[
                            _workstream_card(
                                item["path"],
                                item["eyebrow"],
                                item["label"],
                                item["description"],
                                active=item["path"] == "/overview",
                            )
                            for item in MONITORING_WORKSTREAMS
                        ],
                    ),
                ],
            ),
        ],
    )

    heatmap_section = html.Section(
        id="overview-heatmap",
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("Model RAG Heatmap", className="pd-content-kicker"),
                    html.H3("Cross-Model RAG Comparison"),
                    html.P(f"RAG status across all monitoring dimensions for {latest_period}."),
                ],
            ),
            html.Div(
                className="section-card",
                children=[_rag_heatmap_table(heat_rows)],
            ),
        ],
    )

    trend_section = html.Section(
        id="overview-rag-trend",
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("RAG Trend Analysis", className="pd-content-kicker"),
                    html.H3("Period-over-Period RAG Movement"),
                    html.P(f"Track how {_rag_label(rag_trend_metric)} evolves across monitoring points by model."),
                ],
            ),
            html.Div(
                className="section-card",
                children=[
                    html.Div(
                        className="overview-card-heading-row",
                        children=[
                            html.Div(
                                className="overview-trend-controls",
                                children=[
                                    html.Label("RAG Dimension", className="overview-trend-control-label"),
                                    dcc.Dropdown(
                                        id=RAG_TREND_METRIC_ID,
                                        options=_dropdown_options(RAG_TREND_OPTIONS, RAG_LABELS),
                                        value=rag_trend_metric,
                                        clearable=False,
                                        className="monitoring-top-select",
                                    ),
                                ],
                            ),
                            build_range_controls(RAG_TREND_RANGE_KEY, trend_periods, range_store.get(RAG_TREND_RANGE_KEY)),
                        ],
                    ),
                    _rag_trend_graphs(rows, rag_trend_metric, range_store),
                ],
            ),
        ],
    )

    findings_section = html.Section(
        id="overview-top-findings",
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("Top Findings", className="pd-content-kicker"),
                    html.H3("Red and Amber Findings"),
                    html.P(f"All heatmap RAGs flagged as Red or Amber for {latest_period}."),
                ],
            ),
            html.Div(
                className="section-card",
                children=[_findings_table(findings)],
            ),
        ],
    )

    governance_section = html.Section(
        id="overview-governance-summary",
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-content-heading",
                children=[
                    html.Div("Governance", className="pd-content-kicker"),
                    html.H3("Findings Summary"),
                    html.P("Consolidated view of model risk findings requiring review or escalation."),
                ],
            ),
            html.Div(
                className="section-card",
                children=[
                    html.Div(
                        className="overview-governance-grid",
                        children=[
                            html.Div(
                                className=f"overview-governance-stat overview-governance-stat-red",
                                children=[
                                    html.Div(str(red_findings), className="overview-governance-stat-value"),
                                    html.Div("Red Findings", className="overview-governance-stat-label"),
                                    html.Div("Breaches requiring immediate action", className="overview-governance-stat-desc"),
                                ],
                            ),
                            html.Div(
                                className=f"overview-governance-stat overview-governance-stat-amber",
                                children=[
                                    html.Div(str(amber_findings), className="overview-governance-stat-value"),
                                    html.Div("Amber Findings", className="overview-governance-stat-label"),
                                    html.Div("Review signals under monitoring", className="overview-governance-stat-desc"),
                                ],
                            ),
                            html.Div(
                                className=f"overview-governance-stat overview-governance-stat-green",
                                children=[
                                    html.Div(str(summary["green"]), className="overview-governance-stat-value"),
                                    html.Div("Green Models", className="overview-governance-stat-label"),
                                    html.Div("Models within tolerance", className="overview-governance-stat-desc"),
                                ],
                            ),
                            html.Div(
                                className=f"overview-governance-stat overview-governance-stat-total",
                                children=[
                                    html.Div(str(breaches), className="overview-governance-stat-value"),
                                    html.Div("Total Breaches", className="overview-governance-stat-label"),
                                    html.Div("Red + Amber combined", className="overview-governance-stat-desc"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return [summary_section, heatmap_section, trend_section, findings_section, governance_section]


# ---------------------------------------------------------------------------
# Stores & layout entry points
# ---------------------------------------------------------------------------


def build_stores() -> list:
    """``dcc.Store`` components backing this page's range state."""
    return [
        dcc.Store(id=RANGE_STORE_ID, data={}),
    ]


def build_layout() -> list:
    """Registry entry point: build the page from the loaded dashboard data."""
    from ...data_access import PD_PERFORMANCE_DATA

    return page_layout(PD_PERFORMANCE_DATA)


def page_layout(data: dict) -> list:
    """Top bar + main content for the Overview page."""
    overview_rows = build_overview_rows(data)
    options = overview_filter_options(overview_rows)
    model_options = [value for value in options["models"] if value != "All"]
    return [
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
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Monitoring Point", htmlFor=PERIOD_TOGGLE_ID),
                                        shared_filters.build_single_select_dropdown(
                                            value_id=PERIOD_ID,
                                            toggle_id=PERIOD_TOGGLE_ID,
                                            menu_id=PERIOD_MENU_ID,
                                            filter_key=PERIOD_FILTER_KEY,
                                            options=_dropdown_options(options["periods"]),
                                            value="All",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Segment", htmlFor=SEGMENT_TOGGLE_ID),
                                        shared_filters.build_single_select_dropdown(
                                            value_id=SEGMENT_ID,
                                            toggle_id=SEGMENT_TOGGLE_ID,
                                            menu_id=SEGMENT_MENU_ID,
                                            filter_key=SEGMENT_FILTER_KEY,
                                            options=_dropdown_options(options["segments"]),
                                            value="All",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter monitoring-model-filter",
                                    children=[
                                        html.Label("Specific Models", htmlFor=MODEL_TOGGLE_ID),
                                        shared_filters.build_checkbox_dropdown(
                                            checklist_id=MODEL_ID,
                                            select_all_id=MODEL_SELECT_ALL_ID,
                                            toggle_id=MODEL_TOGGLE_ID,
                                            menu_id=MODEL_MENU_ID,
                                            options=_dropdown_options(model_options),
                                            value=list(model_options),
                                            toggle_label="All models",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="monitoring-filter",
                                    children=[
                                        html.Label("Model Group", htmlFor=MODEL_GROUP_TOGGLE_ID),
                                        shared_filters.build_single_select_dropdown(
                                            value_id=MODEL_GROUP_ID,
                                            toggle_id=MODEL_GROUP_TOGGLE_ID,
                                            menu_id=MODEL_GROUP_MENU_ID,
                                            filter_key=MODEL_GROUP_FILTER_KEY,
                                            options=_dropdown_options(options["groups"]),
                                            value="All",
                                        ),
                                    ],
                                ),
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
                    children=[
                        html.Section(
                            className="pd-content-section pd-live-section",
                            children=[
                                html.Div(
                                    className="pd-performance-note",
                                    children=[
                                        html.Strong("Executive summary: "),
                                        "The Wholesale Portfolio Model Monitoring Overview consolidates RAG outcomes across "
                                        "all monitored credit risk models — PD, LGD, EAD, and Loss — into a single governance-ready "
                                        "view. It surfaces the current health posture, highlights Red and Amber findings that "
                                        "require escalation or review, and tracks period-over-period RAG movements to identify "
                                        "emerging trends before they become material.",
                                    ],
                                ),
                                html.Div(
                                    id=CONTENT_ID,
                                    children=render_overview_content(data, overview_rows),
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
    ]
