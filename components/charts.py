"""Plotly figure builders for the PD Performance dashboard.

Ports the ``drawPd*`` chart-drawing functions from
``pages/monitoring_pd_models_page.py`` to functions that return
``plotly.graph_objects.Figure`` objects for use in ``dcc.Graph``.

Several JS draw functions measured the live DOM element's pixel width
(``chart.clientWidth``) to decide between a stacked (narrow) and side-by-side
(wide, "horizontal") dual-panel layout, and to pick how many x-axis tick
labels to show. There is no equivalent measurement available on the server
when building a Dash figure, so this module always uses the side-by-side
dual-panel layout (matching the original behaviour at desktop widths) and
picks tick density from a fixed ``density`` setting (``"normal"``/``"compact"``)
rather than the live container width. This is documented as a simplification
in the app README.

Charts that had no data in the original simply replaced the chart
``<div>``'s contents with a ``pd-performance-note`` message. Here the
equivalent is a figure with no traces and a centered annotation carrying the
same message, so callbacks can always set ``dcc.Graph(figure=...)``.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..monitoring_config import pd_rag_color
from ..data.mev import calculate_pd_mev_thresholds
from ..data.rank_ordering import (
    build_pd_rank_ordering_period_label_map,
    compare_pd_quarter_labels,
    format_pd_compact_quarter_label,
    get_pd_rank_ordering_scenario_quarter,
    iso_date_to_pd_quarter,
    _pd_quarter_sort_key,
)
from ..data.transformations import (
    _finite,
    build_pd_ae_ratio_bands,
    build_pd_threshold_bands,
    calculate_pd_metric_rag,
    filter_pd_periods_by_range,
    get_pd_thresholds,
    get_pd_threshold_metric_name,
)

AXIS_LINE_COLOR = "#cbd5e1"
GRID_COLOR = "#e5e7eb"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _empty_figure(message: str, height: int = 220) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=height,
        margin=dict(t=18, r=18, b=18, l=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(
            text=message,
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            align="center",
            font=dict(size=13, color="#64748b"),
        )],
    )
    return fig


def _apply_transparent_background(fig: go.Figure) -> None:
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")


def _vertical_marker(x_value, xref="x", yref="paper", color="#64748b", dash="dot", width=1.5):
    return dict(type="line", xref=xref, x0=x_value, x1=x_value, yref=yref, y0=0, y1=1, line=dict(color=color, width=width, dash=dash))


def _build_tick_values(categories: list[str], max_ticks: int) -> list[str]:
    if not categories or len(categories) <= max_ticks:
        return categories
    step = max(2, math.ceil(len(categories) / max_ticks))
    tickvals = [
        value for index, value in enumerate(categories)
        if index == 0 or index == len(categories) - 1 or index % step == 0
    ]
    seen = set()
    deduped = []
    for value in tickvals:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def build_pd_time_series_xaxis(labels, base=None, density="normal", tick_text_map=None):
    """Simplified port of ``buildMonitoringTimeSeriesXAxis``.

    ``density`` selects a fixed tick-count budget (``"compact"`` -> 6,
    ``"normal"`` -> 8, ``"roomy"`` -> 10) instead of one derived from the
    live chart pixel width.
    """
    base = dict(base or {})
    base_tickfont = base.pop("tickfont", {}) or {}
    axis = {**base, "type": base.get("type", "category")}

    categories: list[str] = []
    seen = set()
    for label in labels or []:
        text = str(label or "")
        if text and text not in seen:
            seen.add(text)
            categories.append(text)

    if axis.get("showticklabels") is False or not categories:
        return {**axis, "automargin": True}

    max_ticks = {"compact": 6, "roomy": 10}.get(density, 8)
    tickvals = _build_tick_values(categories, max_ticks)
    is_dense = len(tickvals) < len(categories)
    tick_text_map = tick_text_map or {}

    return {
        **axis,
        "tickmode": "array",
        "tickvals": tickvals,
        "ticktext": [tick_text_map.get(value, value) for value in tickvals],
        "tickangle": base.get("tickangle", -32 if is_dense else 0),
        "automargin": True,
        "tickfont": {"size": 10 if is_dense else 11, **base_tickfont},
    }


def _dual_panel_legend(color: str, label: str, secondary_x_domain: list[float]):
    """Port of the inline "A/E Ratio" / "Notching Difference" / "Delta Accuracy
    Ratio" legend annotation drawn for wide dual-panel charts."""
    x0 = secondary_x_domain[0]
    legend_line_start = x0 + 0.02
    legend_line_end = x0 + 0.075
    legend_marker_center = x0 + 0.0475
    legend_y = 1.09
    shapes = [
        dict(type="line", xref="paper", yref="paper", x0=legend_line_start, x1=legend_line_end, y0=legend_y, y1=legend_y, line=dict(color=color, width=2.5)),
        dict(type="circle", xref="paper", yref="paper", x0=legend_marker_center - 0.006, x1=legend_marker_center + 0.006, y0=legend_y - 0.012, y1=legend_y + 0.012, fillcolor=color, line=dict(color="#ffffff", width=1)),
    ]
    annotations = [
        dict(xref="paper", yref="paper", x=legend_line_end + 0.01, y=legend_y, text=label, showarrow=False, xanchor="left", yanchor="middle", font=dict(size=12, color="#475569")),
    ]
    return shapes, annotations


_DUAL_PANEL_COLUMN_WIDTHS = [0.45, 0.44]
_DUAL_PANEL_HORIZONTAL_SPACING = 0.11
_DUAL_PANEL_SECONDARY_DOMAIN = [0.56, 1.0]


def _make_dual_panel_figure() -> go.Figure:
    return make_subplots(rows=1, cols=2, column_widths=_DUAL_PANEL_COLUMN_WIDTHS, horizontal_spacing=_DUAL_PANEL_HORIZONTAL_SPACING)


# ---------------------------------------------------------------------------
# 1.2 / 1.4 Calibration Conservatism - Calibration Trend
# (drawPdDefaultRateTrend)
# ---------------------------------------------------------------------------


def build_pd_default_rate_trend_figure(performance_trend, monitoring_thresholds, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No portfolio periods are available for the selected snapshot date.")

    quarters = [row["quarter"] for row in trend]
    last_quarter = quarters[-1]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    ae_threshold = next((row for row in thresholds if row.get("metric") == "Actual / Expected Ratio"), {})
    ratios = [row["actual_expected_ratio"] for row in trend]
    ratio_rags = [calculate_pd_metric_rag(thresholds, "Actual / Expected Ratio", ratio) for ratio in ratios]
    ratio_bands = build_pd_ae_ratio_bands(ae_threshold, ratios)

    fig = _make_dual_panel_figure()
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["observed_default_rate"] for row in trend],
        mode="lines+markers", name="Actual Default Rate",
        line=dict(color="#dc2626", width=2.5), marker=dict(size=6),
        hovertemplate="%{x}<br>Actual Default Rate: %{y:.2%}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["predicted_default_rate"] for row in trend],
        mode="lines+markers", name="Predicted Default Rate",
        line=dict(color="#2563eb", width=2.5, dash="dash"), marker=dict(size=6),
        hovertemplate="%{x}<br>Predicted Default Rate: %{y:.2%}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=ratios,
        mode="lines+markers", name="A/E Ratio", showlegend=False,
        line=dict(color="#d97706", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in ratio_rags], line=dict(color="#fff", width=1)),
        customdata=ratio_rags,
        hovertemplate="%{x}<br>A/E Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in ratio_bands["shapes"]]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend("#d97706", "A/E Ratio", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    axis_kwargs = {"title": "Portfolio Quarter", "showline": True, "linecolor": AXIS_LINE_COLOR, "ticks": "outside", "gridcolor": GRID_COLOR}
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="Default Rate", tickformat=".1%", rangemode="tozero", showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="A/E Ratio", standoff=8), range=ratio_bands["axis_range"], showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, automargin=True), row=1, col=2)
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# RAG dot-trend charts (drawPdCalibrationRagTrend / drawPdDiscriminationRagTrend
# / drawPdBalanceSheetCalibrationRagTrend)
# ---------------------------------------------------------------------------


def _rag_score_band_shapes() -> list[dict]:
    return [
        dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=0.5, y1=1.5, fillcolor="rgba(220,38,38,0.08)", line=dict(width=0)),
        dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=1.5, y1=2.5, fillcolor="rgba(217,119,6,0.08)", line=dict(width=0)),
        dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=2.5, y1=3.5, fillcolor="rgba(22,163,74,0.08)", line=dict(width=0)),
    ]


def _rag_score_yaxis(title: str) -> dict:
    return dict(title=title, range=[0.5, 3.5], tickvals=[1, 2, 3], ticktext=["Red (1)", "Amber (2)", "Green (3)"], zeroline=False, gridcolor=GRID_COLOR)


def _format_metric_value(value, decimals=2):
    return "—" if value is None or not _finite(value) else f"{value:.{decimals}f}"


def _rag_dot_figure(quarters, rag_scores, rag_labels, customdata, hovertemplate, monitoring_quarter, yaxis_title) -> go.Figure:
    shapes = _rag_score_band_shapes()
    if monitoring_quarter in quarters:
        shapes.append(_vertical_marker(monitoring_quarter))

    fig = go.Figure(go.Scatter(
        x=quarters, y=rag_scores,
        mode="markers", name="Final RAG",
        marker=dict(color=[pd_rag_color(rag) for rag in rag_labels], size=16, opacity=0.95, line=dict(color="#ffffff", width=1)),
        customdata=customdata,
        hovertemplate=hovertemplate,
    ))
    fig.update_layout(
        height=290,
        margin=dict(t=18, r=28, b=54, l=78),
        hovermode="closest",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Monitoring Point", "gridcolor": GRID_COLOR}, density="compact"),
        yaxis=_rag_score_yaxis(yaxis_title),
    )
    _apply_transparent_background(fig)
    return fig


def build_pd_calibration_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No calibration-conservatism RAG periods are available for the selected monitoring point.")

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [row["rag"], _format_metric_value(row["weighted_average"], 2), "—" if row["rounded_score"] is None or not _finite(row["rounded_score"]) else f"{row['rounded_score']}"]
        for row in trend
    ]
    return _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Calibration Conservatism RAG (ECL PIT): %{customdata[0]}<br>Weighted score: %{customdata[1]}<br>Rounded score: %{customdata[2]}<extra></extra>",
        monitoring_quarter,
        "Calibration Conservatism Score",
    )


def build_pd_discrimination_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No discriminatory-power RAG periods are available for the selected monitoring point.")

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [
            row["rag"],
            _format_metric_value(row["accuracy_ratio"], 3),
            row.get("accuracy_rag") or "N/A",
            _format_metric_value(row["delta_accuracy_ratio"], 3),
            row.get("delta_accuracy_rag") or "N/A",
            f"{row['default_count_1y']}" if _finite(row.get("default_count_1y")) else "—",
            "Yes" if row.get("low_default_override") else "No",
        ]
        for row in trend
    ]
    return _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Discriminatory Power RAG: %{customdata[0]}<br>Accuracy Ratio 1 year: %{customdata[1]} (%{customdata[2]})<br>"
        "Delta Accuracy Ratio 1 year: %{customdata[3]} (%{customdata[4]})<br>Default 1 year count: %{customdata[5]}<br>"
        "Low-default override: %{customdata[6]}<extra></extra>",
        monitoring_quarter,
        "Discriminatory Power Score",
    )


def build_pd_balance_sheet_calibration_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No balance sheet calibration-conservatism RAG periods are available for the selected monitoring point.")

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [
            row["rag"],
            row.get("assignment_rag") or "N/A",
            "—" if row["confidence_interval"] is None or not _finite(row["confidence_interval"]) else f"{row['confidence_interval'] * 100:.2f}%",
            row.get("confidence_rag") or "N/A",
            "—" if row["notching_difference"] is None or not _finite(row["notching_difference"]) else f"{round(row['notching_difference'])}",
            row.get("notching_rag") or "N/A",
        ]
        for row in trend
    ]
    return _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Calibration Conservatism RAG (ECL PIT): %{customdata[0]}<br>RAG Assignment: %{customdata[1]}<br>"
        "Confidence Interval: %{customdata[2]} (%{customdata[3]})<br>Notching Test: %{customdata[4]} (%{customdata[5]})<extra></extra>",
        monitoring_quarter,
        "Calibration Conservatism Score",
    )


# ---------------------------------------------------------------------------
# 1.2 / 1.4 Calibration Conservatism - Notching Trend (drawPdNotchingTrend)
# ---------------------------------------------------------------------------


def build_pd_notching_trend_figure(performance_trend, monitoring_thresholds, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No notching periods are available for the selected snapshot date.")

    quarters = [row["quarter"] for row in trend]
    last_quarter = quarters[-1]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    threshold = next((row for row in thresholds if row.get("metric") == "Notching Test"), {})
    differences = [row["notching_difference"] for row in trend]
    difference_rags = [calculate_pd_metric_rag(thresholds, "Notching Test", value) for value in differences]
    difference_bands = build_pd_threshold_bands(threshold, differences, {"min_axis_max": 2})

    fig = _make_dual_panel_figure()
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["actual_notch"] for row in trend],
        mode="lines+markers", name="Actual Notch",
        line=dict(color="#dc2626", width=2.5), marker=dict(size=6),
        hovertemplate="%{x}<br>Actual Notch: %{y:.0f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["predicted_notch"] for row in trend],
        mode="lines+markers", name="Predicted Notch",
        line=dict(color="#2563eb", width=2.5, dash="dash"), marker=dict(size=6),
        hovertemplate="%{x}<br>Predicted Notch: %{y:.0f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=differences,
        mode="lines+markers", name="Notching Difference", showlegend=False,
        line=dict(color="#d97706", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in difference_rags], line=dict(color="#fff", width=1)),
        customdata=difference_rags,
        hovertemplate="%{x}<br>Notching Difference: %{y:.0f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in difference_bands["shapes"]]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend("#d97706", "Notching Difference", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    axis_kwargs = {"title": "Portfolio Quarter", "showline": True, "linecolor": AXIS_LINE_COLOR, "ticks": "outside", "gridcolor": GRID_COLOR}
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="CRR Notch", tickmode="linear", dtick=1, range=[0.5, 9.5], showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="Notching Difference", standoff=8), range=difference_bands["axis_range"], tickmode="linear", dtick=1, showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, automargin=True), row=1, col=2)
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 1.2 / 1.4 Calibration Conservatism - Confidence Interval Trend
# (drawPdConfidenceIntervalTrend)
# ---------------------------------------------------------------------------


def build_pd_confidence_interval_trend_figure(performance_trend, monitoring_thresholds, snapshot_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No confidence-interval periods are available for the selected snapshot date.")

    quarters = [row["quarter"] for row in trend]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    metric_name = get_pd_threshold_metric_name("Confidence Interval Test")
    threshold = next((row for row in thresholds if row.get("metric") == metric_name), {})
    confidence_values = [row["confidence_interval"] for row in trend]
    confidence_rags = [calculate_pd_metric_rag(thresholds, "Confidence Interval Test", value) for value in confidence_values]
    confidence_bands = build_pd_threshold_bands(threshold, confidence_values, {"min_axis_max": 1})

    shapes = list(confidence_bands["shapes"])
    if snapshot_quarter in quarters:
        shapes.append(_vertical_marker(snapshot_quarter))

    fig = go.Figure(go.Scatter(
        x=quarters, y=confidence_values,
        mode="lines+markers", name="Confidence Interval Test",
        line=dict(color="#16a34a", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in confidence_rags], line=dict(color="#fff", width=1)),
        customdata=confidence_rags,
        hovertemplate="%{x}<br>Confidence Interval Test: %{y:.1%}<br>RAG: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=340,
        margin=dict(t=18, r=30, b=52, l=68),
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.08),
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Portfolio Quarter", "gridcolor": GRID_COLOR}, density="compact"),
        yaxis=dict(title="Confidence Interval Test", tickformat=".0%", range=confidence_bands["axis_range"], gridcolor=GRID_COLOR),
    )
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 1.3 Discriminatory Power - Other Metrics Trend (drawPdDiscriminationTrend)
# ---------------------------------------------------------------------------

_DISCRIMINATION_TREND_METRICS = [
    {"key": "gini_coefficient", "name": "Gini Coefficient", "color": "#7c3aed", "dash": "dash"},
    {"key": "ks_statistic", "name": "KS Statistic", "color": "#d97706", "dash": "dot"},
    {"key": "kendall_tau", "name": "Kendall's Tau", "color": "#0891b2", "dash": "dashdot"},
]


def build_pd_discrimination_trend_figures(performance_trend, monitoring_thresholds, snapshot_quarter, range_value=None) -> dict[str, go.Figure]:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        message = _empty_figure("No portfolio periods are available for the selected snapshot date.", height=296)
        return {metric["key"]: message for metric in _DISCRIMINATION_TREND_METRICS}

    quarters = [row["quarter"] for row in trend]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    figures: dict[str, go.Figure] = {}
    for metric in _DISCRIMINATION_TREND_METRICS:
        values = [row[metric["key"]] for row in trend]
        rags = [calculate_pd_metric_rag(thresholds, metric["name"], value) for value in values]
        threshold = next((row for row in thresholds if row.get("metric") == metric["name"]), {})
        bands = build_pd_threshold_bands(threshold, values)
        shapes = list(bands["shapes"])
        if snapshot_quarter in quarters:
            shapes.append(_vertical_marker(snapshot_quarter))

        fig = go.Figure(go.Scatter(
            x=quarters, y=values,
            mode="lines+markers", name=metric["name"], connectgaps=False,
            line=dict(color=metric["color"], width=2.5, dash=metric["dash"]),
            marker=dict(size=8, color=[pd_rag_color(rag) for rag in rags], line=dict(color="#fff", width=1)),
            customdata=rags,
            hovertemplate=f"%{{x}}<br>{metric['name']}: %{{y:.3f}}<br>RAG: %{{customdata}}<extra></extra>",
        ))
        fig.update_layout(
            height=296,
            margin=dict(t=18, r=20, b=42, l=52),
            hovermode="x unified",
            showlegend=False,
            shapes=shapes,
            xaxis=build_pd_time_series_xaxis(quarters, {"title": "Portfolio Quarter", "gridcolor": GRID_COLOR}, density="compact"),
            yaxis=dict(title=metric["name"], range=bands["axis_range"], gridcolor=GRID_COLOR, zerolinecolor=AXIS_LINE_COLOR),
        )
        _apply_transparent_background(fig)
        figures[metric["key"]] = fig
    return figures


# ---------------------------------------------------------------------------
# 1.3 Discriminatory Power - Accuracy Ratio / Go-Live Delta Trend
# (drawPdGoLiveAccuracyTrend)
# ---------------------------------------------------------------------------


def build_pd_go_live_accuracy_trend_figure(performance_trend, monitoring_thresholds, go_live_quarter, range_value=None) -> go.Figure:
    if not go_live_quarter:
        return _empty_figure("No go-live quarter between 2019Q2 and 2019Q4 is available for the selected population.")

    go_live_periods = [row["quarter"] for row in performance_trend if row["quarter"] and row["quarter"] >= go_live_quarter]
    periods = filter_pd_periods_by_range(range_value, go_live_periods)
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No discriminatory-power accuracy periods are available for the selected snapshot date.")

    quarters = [row["quarter"] for row in trend]
    last_quarter = quarters[-1]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    delta_threshold = next((row for row in thresholds if row.get("metric") == "Delta Accuracy Ratio"), {})
    delta_values = [row["delta_accuracy_ratio"] for row in trend]
    delta_rags = [calculate_pd_metric_rag(thresholds, "Delta Accuracy Ratio", value) for value in delta_values]
    delta_bands = build_pd_threshold_bands(delta_threshold, delta_values, {"min_axis_max": 0.3})

    fig = _make_dual_panel_figure()
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["accuracy_ratio"] for row in trend],
        mode="lines+markers", name="Accuracy Ratio",
        line=dict(color="#2563eb", width=2.5), marker=dict(size=6),
        hovertemplate="%{x}<br>Accuracy Ratio: %{y:.3f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=[row["go_live_accuracy_ratio"] for row in trend],
        mode="lines", name="Go Live Accuracy Ratio",
        line=dict(color="#0f766e", width=2, dash="dash"),
        hovertemplate=f"%{{x}}<br>Go Live Accuracy Ratio: %{{y:.3f}}<br>Go-live quarter: {go_live_quarter}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=quarters, y=delta_values,
        mode="lines+markers", name="Delta Accuracy Ratio", showlegend=False,
        line=dict(color="#d97706", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in delta_rags], line=dict(color="#fff", width=1)),
        customdata=delta_rags,
        hovertemplate="%{x}<br>Delta Accuracy Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in delta_bands["shapes"]]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend("#d97706", "Delta Accuracy Ratio", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, {"title": "Portfolio Quarter", "showline": True, "linecolor": AXIS_LINE_COLOR, "ticks": "outside", "gridcolor": GRID_COLOR}, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, {"title": f"Portfolio Quarter (from {go_live_quarter})", "showline": True, "linecolor": AXIS_LINE_COLOR, "ticks": "outside", "gridcolor": GRID_COLOR}, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="Accuracy Ratio", showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, zerolinecolor=AXIS_LINE_COLOR, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="Delta Accuracy Ratio", standoff=8), range=delta_bands["axis_range"], showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside", gridcolor=GRID_COLOR, zerolinecolor=AXIS_LINE_COLOR, automargin=True), row=1, col=2)
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 2.4 Scenario Rank Ordering (drawPdRankOrderingChart)
# ---------------------------------------------------------------------------


def build_pd_rank_ordering_figure(aggregate, y_title: str, range_value=None) -> go.Figure:
    all_periods = aggregate.get("periods") or []
    visible_periods = filter_pd_periods_by_range(range_value, all_periods)
    severe_dates = aggregate.get("severe_dates") or []
    scenario_quarter = get_pd_rank_ordering_scenario_quarter(severe_dates)

    axis_periods = list(visible_periods)
    if (
        scenario_quarter
        and visible_periods
        and scenario_quarter not in axis_periods
        and compare_pd_quarter_labels(scenario_quarter, visible_periods[0]) >= 0
        and compare_pd_quarter_labels(scenario_quarter, visible_periods[-1]) <= 0
    ):
        axis_periods.append(scenario_quarter)
        axis_periods.sort(key=_pd_quarter_sort_key)

    period_label_map = build_pd_rank_ordering_period_label_map(axis_periods, severe_dates, hide_scenario_quarter=True)
    historical = [point for point in aggregate.get("historical") or [] if point["period"] in visible_periods]
    base = [point for point in aggregate.get("base") or [] if point["period"] in visible_periods]
    severe = [point for point in aggregate.get("severe") or [] if point["period"] in visible_periods]
    has_series = historical or base or severe
    if not visible_periods or not has_series:
        return _empty_figure("No scenario PD data is available for the selected time window.")

    all_values = [point["value"] for point in (*historical, *base, *severe) if _finite(point["value"])]
    if not all_values:
        return _empty_figure("No scenario PD data is available for the selected time window.")

    min_value = min(all_values)
    max_value = max(all_values)
    padding = max((max_value - min_value) * 0.12, abs(max_value or 1) * 0.08, 0.0025)
    y_min = max(0, min_value - padding)
    y_max = max_value + padding

    severe_quarters = sorted(
        {iso_date_to_pd_quarter(date) for date in severe_dates if iso_date_to_pd_quarter(date) in axis_periods},
        key=_pd_quarter_sort_key,
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[point["period"] for point in historical], y=[point["value"] for point in historical],
        mode="lines", name="Historical PD",
        line=dict(color="#2563eb", width=2.6),
        customdata=[period_label_map.get(point["period"], format_pd_compact_quarter_label(point["period"])) for point in historical],
        hovertemplate="%{customdata}<br>Historical PD: %{y:.2%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[point["period"] for point in base], y=[point["value"] for point in base],
        mode="lines", name="Base PD",
        line=dict(color="#64748b", width=2.4),
        customdata=[period_label_map.get(point["period"], format_pd_compact_quarter_label(point["period"])) for point in base],
        hovertemplate="%{customdata}<br>Base PD: %{y:.2%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[point["period"] for point in severe], y=[point["value"] for point in severe],
        mode="lines", name="Severe PD",
        line=dict(color="#dc2626", width=2.5),
        customdata=[period_label_map.get(point["period"], format_pd_compact_quarter_label(point["period"])) for point in severe],
        hovertemplate="%{customdata}<br>Severe PD: %{y:.2%}<extra></extra>",
    ))
    if severe_quarters:
        x_values: list = []
        y_values: list = []
        for quarter in severe_quarters:
            x_values += [quarter, quarter, None]
            y_values += [y_min, y_max, None]
        fig.add_trace(go.Scatter(
            x=x_values, y=y_values,
            mode="lines", name="Severe scenario date",
            line=dict(color="#7c2d12", width=1.4, dash="dot"),
            hoverinfo="skip",
        ))

    fig.update_layout(
        height=320,
        margin=dict(t=18, r=24, b=48, l=62),
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.12),
        xaxis=build_pd_time_series_xaxis(axis_periods, {
            "title": "Quarter", "gridcolor": GRID_COLOR, "showline": True, "linecolor": AXIS_LINE_COLOR,
            "ticks": "outside", "categoryorder": "array", "categoryarray": axis_periods,
        }, density="compact", tick_text_map=period_label_map),
        yaxis=dict(title=y_title, tickformat=".1%", range=[y_min, y_max], gridcolor=GRID_COLOR, zerolinecolor=AXIS_LINE_COLOR, showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside"),
    )
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 2.6 MEV Range (drawPdMevRangeChart)
# ---------------------------------------------------------------------------


def build_pd_mev_range_figure(model_data, mev_name: str, mev_data, color: str, range_value=None) -> go.Figure:
    all_points = sorted(
        ((quarter, value) for quarter, value in (mev_data.get("time_series") or {}).items() if _finite(value)),
        key=lambda item: _pd_quarter_sort_key(item[0]),
    )
    visible_quarters = set(filter_pd_periods_by_range(range_value, [point[0] for point in all_points]))
    points = [point for point in all_points if point[0] in visible_quarters]
    if not points:
        return _empty_figure("No MEV time-series data is available for the selected time window.", height=292)

    thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
    quarters = [point[0] for point in points]
    values = [point[1] for point in points]
    development_quarter = iso_date_to_pd_quarter(mev_data.get("dev_range", {}).get("development_date"))
    severe_quarter = iso_date_to_pd_quarter(model_data.get("severe_scenario_date"))

    all_y_values = list(values)
    if thresholds:
        all_y_values += [thresholds["green_min"], thresholds["green_max"], thresholds["amber_lower"], thresholds["amber_upper"]]
    min_value = min(all_y_values)
    max_value = max(all_y_values)
    padding = max((max_value - min_value) * 0.08, abs(max_value or 1) * 0.05, 0.25)
    y_min = min_value - padding
    y_max = max_value + padding

    shapes = []
    if thresholds:
        green_min = thresholds["green_min"]
        green_max = thresholds["green_max"]
        amber_lower = thresholds["amber_lower"]
        amber_upper = thresholds["amber_upper"]
        red = "rgba(220,38,38,0.14)"
        amber = "rgba(217,119,6,0.20)"
        green = "rgba(22,163,74,0.16)"
        shapes.extend([
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=y_min, y1=amber_lower, fillcolor=red, line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=amber_lower, y1=green_min, fillcolor=amber, line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_min, y1=green_max, fillcolor=green, line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_max, y1=amber_upper, fillcolor=amber, line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=amber_upper, y1=y_max, fillcolor=red, line=dict(width=0), layer="below"),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_min, y1=green_min, line=dict(color="rgba(22,163,74,0.9)", width=1.8)),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_max, y1=green_max, line=dict(color="rgba(22,163,74,0.9)", width=1.8)),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=amber_lower, y1=amber_lower, line=dict(color="rgba(217,119,6,0.82)", width=1.4, dash="dash")),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=amber_upper, y1=amber_upper, line=dict(color="rgba(217,119,6,0.82)", width=1.4, dash="dash")),
        ])

    if development_quarter and development_quarter in quarters:
        shapes.append(_vertical_marker(development_quarter, color="#0f172a", dash="dot"))
    if severe_quarter and severe_quarter in quarters:
        shapes.append(_vertical_marker(severe_quarter, color="#9a3412", dash="dash"))

    fig = go.Figure(go.Scatter(
        x=quarters, y=values,
        mode="lines+markers", connectgaps=False,
        line=dict(color=color, width=2.6, shape="spline", smoothing=0.45),
        marker=dict(size=6, color="#ffffff", line=dict(color=color, width=2)),
        hovertemplate=f"%{{x}}<br>{mev_name}: %{{y:,.2f}}<extra></extra>",
    ))
    fig.update_layout(
        height=292,
        margin=dict(t=16, r=18, b=54, l=58),
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": "#e2e8f0", "showline": True, "linecolor": AXIS_LINE_COLOR, "ticks": "outside"}, density="compact"),
        yaxis=dict(title=mev_name, range=[y_min, y_max], automargin=True, gridcolor="#e2e8f0", zerolinecolor=AXIS_LINE_COLOR, showline=True, linecolor=AXIS_LINE_COLOR, ticks="outside"),
    )
    _apply_transparent_background(fig)
    return fig
