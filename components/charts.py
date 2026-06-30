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

import calendar
from datetime import date, datetime, timedelta
import math
import re
import statistics

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..data.analytics.constants import pd_rag_color
from ..data.analytics.mev_range import (
    calculate_pd_mev_thresholds,
    get_pd_mev_scenario_quarter,
    get_pd_mev_scenario_series,
)
from ..data.analytics.quarter_labels import (
    compare_pd_quarter_labels,
    format_pd_compact_quarter_label,
    iso_date_to_pd_quarter,
    _pd_quarter_sort_key,
)
from ..data.analytics.calculations import (
    _finite,
    build_pd_ae_ratio_bands,
    build_pd_threshold_bands,
    calculate_pd_metric_rag,
    filter_pd_periods_by_range,
    get_pd_thresholds,
    get_pd_threshold_metric_name,
)

AXIS_LINE_COLOR = "#cbd5e1"
GRID_COLOR = "#cbd5e1"
SAAS_SCENARIO_COLOR_MAP = {
    "baseline": "#16a34a",
    "intsevere": "#dc2626",
    "baseline_2std_shock": "#b91c1c",
    "other": "#2563eb",
}
SAAS_SCENARIO_FALLBACK_COLORS = ["#0f766e", "#d97706", "#0891b2", "#7c2d12"]
SAAS_DARK_SCENARIO_COLOR_MAP = {
    "baseline": "#86efac",
    "intsevere": "#fb7185",
    "baseline_2std_shock": "#f43f5e",
    "other": "#7dd3fc",
}
SAAS_DARK_SCENARIO_FALLBACK_COLORS = ["#c4b5fd", "#fbbf24", "#67e8f9", "#f472b6"]
SAAS_SCENARIO_ORDER = {"baseline": 0, "other": 1, "intsevere": 2, "baseline_2std_shock": 3}
SAAS_SCENARIO_LABEL_MAP = {
    "baseline": "Baseline",
    "intsevere": "Severe",
    "baseline_2std_shock": "Baseline + 2SD Shock",
    "other": "Other",
}
SAAS_RUN_FOR_DASHES = ["solid", "dot", "dash", "dashdot"]
SAAS_THEME_PALETTES = {
    "light": {
        "empty_message": "#64748b",
        "marker_fill": "#ffffff",
        "year_band_fill": "rgba(148,163,184,0.055)",
        "projection_band_fill": "rgba(148,163,184,0.045)",
        "projection_marker": "#94a3b8",
        "annotation_bg": "rgba(255,255,255,0.82)",
        "annotation_text": "#64748b",
        "legend_title": "#64748b",
        "legend_bg": "rgba(255,255,255,0.92)",
        "legend_border": "rgba(203,213,225,0.92)",
        "legend_font": "#334155",
        "axis_title": "#334155",
        "axis_tick": "#475569",
        "grid_color": "#e2e8f0",
        "axis_line": AXIS_LINE_COLOR,
        "zero_line": "#cbd5e1",
        "spike_color": "#94a3b8",
        "development_marker": "#0f172a",
        "scenario_date_marker": "#dc2626",
        "minmax_fill": "rgba(37,99,235,0.06)",
        "hover_bg": "rgba(15,23,42,0.95)",
        "hover_font": "#f8fafc",
    },
    "dark": {
        "empty_message": "#a7b4c8",
        "marker_fill": "#111c2f",
        "year_band_fill": "rgba(148,163,184,0.10)",
        "projection_band_fill": "rgba(125,211,252,0.08)",
        "projection_marker": "#a7b4c8",
        "annotation_bg": "rgba(17,28,47,0.92)",
        "annotation_text": "#d8e1ee",
        "legend_title": "#a7b4c8",
        "legend_bg": "rgba(17,28,47,0.94)",
        "legend_border": "rgba(148,163,184,0.28)",
        "legend_font": "#d8e1ee",
        "axis_title": "#d8e1ee",
        "axis_tick": "#a7b4c8",
        "grid_color": "rgba(148,163,184,0.18)",
        "axis_line": "rgba(148,163,184,0.34)",
        "zero_line": "rgba(148,163,184,0.34)",
        "spike_color": "#7dd3fc",
        "development_marker": "#f6f8fc",
        "scenario_date_marker": "#fb7185",
        "minmax_fill": "rgba(125,211,252,0.12)",
        "hover_bg": "rgba(8,17,31,0.96)",
        "hover_font": "#f6f8fc",
    },
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _normalize_saas_theme(theme: str | None) -> str:
    return theme if theme in SAAS_THEME_PALETTES else "light"


def _saas_theme_palette(theme: str | None) -> dict[str, str]:
    return SAAS_THEME_PALETTES[_normalize_saas_theme(theme)]


def _monitoring_trend_line_color(theme: str | None) -> str:
    normalized = _normalize_saas_theme(theme)
    return "rgba(203,213,225,0.78)" if normalized == "dark" else "rgba(71,85,105,0.75)"


def _empty_figure(message: str, height: int = 220, *, theme: str = "light") -> go.Figure:
    palette = _saas_theme_palette(theme)
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
            font=dict(size=13, color=palette["empty_message"]),
        )],
    )
    return fig


def _apply_transparent_background(fig: go.Figure) -> None:
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")


def _vertical_marker(x_value, xref="x", yref="paper", color="#64748b", dash="dot", width=1.5):
    return dict(type="line", xref=xref, x0=x_value, x1=x_value, yref=yref, y0=0, y1=1, line=dict(color=color, width=width, dash=dash))


def _saas_scenario_color(
    scenario: str,
    scenario_colors: dict[str, str],
    *,
    base_colors: dict[str, str] | None = None,
    fallback_colors: list[str] | None = None,
) -> str:
    normalized_scenario = str(scenario or "").strip().lower()
    base_colors = base_colors or SAAS_SCENARIO_COLOR_MAP
    fallback_colors = fallback_colors or SAAS_SCENARIO_FALLBACK_COLORS
    if normalized_scenario in scenario_colors:
        return scenario_colors[normalized_scenario]
    if normalized_scenario in base_colors:
        return base_colors[normalized_scenario]
    color = fallback_colors[len(scenario_colors) % len(fallback_colors)]
    scenario_colors[normalized_scenario] = color
    return color


def _format_saas_scenario_label(scenario: str) -> str:
    normalized_scenario = str(scenario or "").strip().lower()
    if normalized_scenario in SAAS_SCENARIO_LABEL_MAP:
        return SAAS_SCENARIO_LABEL_MAP[normalized_scenario]
    if not normalized_scenario:
        return "Scenario"
    return normalized_scenario.replace("_", " ").title()


def _build_tick_values(categories: list[str], max_ticks: int) -> list[str]:
    if not categories or len(categories) <= max_ticks:
        return categories
    step = max(2, math.ceil(len(categories) / max_ticks))
    last_index = len(categories) - 1
    tickvals = [
        value for index, value in enumerate(categories)
        if index % step == 0
    ]
    # Add the last label only when it isn't immediately adjacent to the previous
    # step tick — a gap of 1 causes horizontal labels to visually overlap.
    last_step_index = (last_index // step) * step
    if last_step_index < last_index and (last_index - last_step_index) > 1:
        tickvals.append(categories[last_index])
    seen = set()
    deduped = []
    for value in tickvals:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _format_saas_quarter_value(quarter_value) -> str:
    if quarter_value is None:
        return ""
    try:
        return str(int(round(quarter_value)))
    except (TypeError, ValueError):
        return str(quarter_value)


def _format_saas_quarter_label(date_value) -> str:
    parsed_date = _coerce_saas_date(date_value)
    if parsed_date is None:
        return str(date_value).strip() if date_value is not None else ""
    year = parsed_date.year
    month = parsed_date.month
    quarter = ((month - 1) // 3) + 1
    return f"{year}Q{quarter}"


def _coerce_saas_date(date_value) -> date | None:
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value.date()
    if isinstance(date_value, date):
        return date_value
    if hasattr(date_value, "to_pydatetime"):
        return date_value.to_pydatetime().date()
    text = str(date_value).strip()
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _build_saas_date_ticks(date_values, max_ticks: int = 8):
    categories = []
    seen = set()
    for value in sorted(date_value for date_value in (date_values or []) if date_value is not None):
        key = value.isoformat() if hasattr(value, "isoformat") else str(value)
        if key in seen:
            continue
        seen.add(key)
        categories.append(value)

    if len(categories) <= max_ticks:
        return categories

    step = max(2, math.ceil(len(categories) / max_ticks))
    tickvals = [
        value for index, value in enumerate(categories)
        if index == 0 or index == len(categories) - 1 or index % step == 0
    ]
    deduped = []
    seen = set()
    for value in tickvals:
        key = value.isoformat() if hasattr(value, "isoformat") else str(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _saas_history_year_band_shapes(date_values, *, fillcolor: str = "rgba(148,163,184,0.055)") -> list[dict]:
    parsed_dates = sorted(
        parsed_date
        for parsed_date in (_coerce_saas_date(value) for value in (date_values or []))
        if parsed_date is not None
    )
    if len(parsed_dates) < 2:
        return []

    years = sorted({parsed_date.year for parsed_date in parsed_dates})
    shapes: list[dict] = []
    for index, year_value in enumerate(years):
        if index % 2 == 0:
            continue
        shapes.append(
            dict(
                type="rect",
                xref="x",
                x0=date(year_value, 1, 1),
                x1=date(year_value + 1, 1, 1),
                yref="paper",
                y0=0,
                y1=1,
                fillcolor=fillcolor,
                line=dict(width=0),
                layer="below",
            )
        )
    return shapes


def _format_saas_legend_label(
    *,
    model_label: str,
    scenario_label: str,
    multiple_models: bool,
    run_for: str | None = None,
    multiple_run_fors: bool = False,
    compact: bool = False,
) -> str:
    compact_scenario_label = {
        "Baseline": "Base",
        "Severe": "Severe",
        "Other": "Other",
    }.get(scenario_label, scenario_label)

    base_label = compact_scenario_label if compact else scenario_label
    if multiple_models:
        label = f"{model_label} · {base_label}" if compact else f"{model_label}: {base_label}"
    else:
        label = base_label

    if multiple_run_fors and run_for:
        label = f"{run_for} {label}"

    return label


def _compact_run_for_label(run_for: str) -> str:
    tokens = run_for.strip().split()
    if tokens and tokens[-1].isdigit() and len(tokens[-1]) == 4:
        return f"'{tokens[-1][-2:]}"
    return run_for


def _format_projection_quarter_label(quarter_value) -> str:
    if quarter_value is None or not _finite(quarter_value):
        return ""
    numeric_value = float(quarter_value)
    if numeric_value.is_integer():
        return f"Q{int(numeric_value)}"
    return f"Q{numeric_value:g}"


def _saas_quarter_for_date(records, target_date):
    target = _coerce_saas_date(target_date)
    if target is None:
        return None
    for row in records or []:
        row_date = _coerce_saas_date(row.get("Date"))
        quarter_value = row.get("Quarter")
        if row_date == target and _finite(quarter_value):
            return float(quarter_value)
    return None


def _saas_monitoring_axis_range(visible_values: list[float], band_spec: dict | None) -> tuple[float | None, float | None]:
    y_candidates = list(visible_values or [])
    if band_spec:
        y_candidates.extend([
            band_spec["green_low"],
            band_spec["green_high"],
            band_spec["amber_low_low"],
            band_spec["amber_high_high"],
        ])
    if not y_candidates:
        return None, None

    y_min = min(y_candidates)
    y_max = max(y_candidates)
    y_span = y_max - y_min
    base_scale = max(abs(y_min), abs(y_max), 1.0)
    y_padding = y_span * 0.12 if not math.isclose(y_span, 0.0) else base_scale * 0.12
    y_padding = max(y_padding, base_scale * 0.03, 0.18)

    axis_low = y_min - y_padding
    axis_high = y_max + y_padding
    if math.isclose(axis_low, axis_high):
        axis_low -= 1.0
        axis_high += 1.0
    return axis_low, axis_high


def _saas_monitoring_x_range(axis_values, *, is_projection_only: bool, development_date=None, current_date=None):
    x_candidates = [value for value in (axis_values or []) if value is not None]
    if is_projection_only:
        dev_quarter = development_date if isinstance(development_date, (int, float)) else None
        current_quarter = current_date if isinstance(current_date, (int, float)) else None
        if dev_quarter is not None:
            x_candidates.append(float(dev_quarter))
        if current_quarter is not None:
            x_candidates.append(float(current_quarter))
        if not x_candidates:
            return None
        return [min(x_candidates) - 0.6, max(x_candidates) + 0.6]

    parsed_dates = [
        parsed_date
        for parsed_date in (_coerce_saas_date(value) for value in x_candidates)
        if parsed_date is not None
    ]
    for marker_value in (development_date, current_date):
        parsed_marker = _coerce_saas_date(marker_value)
        if parsed_marker is not None:
            parsed_dates.append(parsed_marker)
    if not parsed_dates:
        return None

    start_date = min(parsed_dates)
    end_date = max(parsed_dates)
    span_days = (end_date - start_date).days
    pad_days = max(int(span_days * 0.05), 45) if span_days > 0 else 45
    return [start_date - timedelta(days=pad_days), end_date + timedelta(days=pad_days)]


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

    max_ticks = {"tight": 4, "compact": 6, "roomy": 10}.get(density, 8)
    tickvals = _build_tick_values(categories, max_ticks)
    is_dense = len(tickvals) < len(categories)
    tick_text_map = {
        value: format_pd_compact_quarter_label(value)
        for value in categories
        if format_pd_compact_quarter_label(value) != value
    } | (tick_text_map or {})

    return {
        **axis,
        "tickmode": "array",
        "tickvals": tickvals,
        "ticktext": [tick_text_map.get(value, value) for value in tickvals],
        "tickangle": base.get("tickangle", 0),
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


def build_pd_default_rate_trend_figure(performance_trend, monitoring_thresholds, range_value=None, *, theme: str = "light") -> go.Figure:
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
    ratio_grid_color = "rgba(148,163,184,0.18)"
    ratio_grid_width = 0.8
    trend_line_color = _monitoring_trend_line_color(theme)

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
        line=dict(color=trend_line_color, width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in ratio_rags], line=dict(color="#fff", width=1)),
        customdata=ratio_rags,
        hovertemplate="%{x}<br>A/E Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in ratio_bands["shapes"]]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend(trend_line_color, "A/E Ratio", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    axis_kwargs = {"title": "Quarter", "gridcolor": ratio_grid_color, "gridwidth": ratio_grid_width}
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="Default Rate", tickformat=".1%", rangemode="tozero", gridcolor=ratio_grid_color, gridwidth=ratio_grid_width, zeroline=False, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="A/E Ratio", standoff=8), range=ratio_bands["axis_range"], gridcolor=ratio_grid_color, gridwidth=ratio_grid_width, zeroline=False, automargin=True), row=1, col=2)
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
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"),
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
# LGD / EAD shared chart helpers
# ---------------------------------------------------------------------------


def _lgd_thresholds(monitoring_thresholds) -> list[dict]:
    return list((monitoring_thresholds or {}).get("lgd_thresholds") or [])


# ---------------------------------------------------------------------------
# LGD RAG trend charts
# ---------------------------------------------------------------------------


def build_lgd_calibration_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No calibration-conservatism RAG periods are available for the selected monitoring point.")

    def pct(value):
        return "—" if value is None or not _finite(value) else f"{value * 100:.2f}%"

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [
            row["rag"],
            pct(row.get("me")),
            row.get("me_rag") or "N/A",
            pct(row.get("rmse")),
            row.get("rmse_rag") or "N/A",
            "—" if row.get("weighted_average") is None or not _finite(row.get("weighted_average")) else f"{row['weighted_average']:.2f}",
            "—" if row.get("rounded_score") is None or not _finite(row.get("rounded_score")) else f"{row['rounded_score']}",
        ]
        for row in trend
    ]
    fig = _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Calibration Conservatism RAG: %{customdata[0]}<br>"
        "Mean Error 1 year: %{customdata[1]} (%{customdata[2]})<br>"
        "RMSE 1 year: %{customdata[3]} (%{customdata[4]})<br>"
        "Weighted score: %{customdata[5]}<br>Rounded score: %{customdata[6]}<extra></extra>",
        monitoring_quarter,
        "Calibration Conservatism Score",
    )
    fig.update_layout(xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"))
    return fig


def build_lgd_discrimination_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No discriminatory-power RAG periods are available for the selected monitoring point.")

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [
            row["rag"],
            _format_metric_value(row.get("kendall_tau"), 3),
            row.get("kendall_tau_rag") or "N/A",
            "—" if row.get("weighted_average") is None or not _finite(row.get("weighted_average")) else f"{row['weighted_average']:.2f}",
            "—" if row.get("rounded_score") is None or not _finite(row.get("rounded_score")) else f"{row['rounded_score']}",
        ]
        for row in trend
    ]
    fig = _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Discriminatory Power RAG: %{customdata[0]}<br>"
        "Kendall's Tau 1 year: %{customdata[1]} (%{customdata[2]})<br>"
        "Weighted score: %{customdata[3]}<br>Rounded score: %{customdata[4]}<extra></extra>",
        monitoring_quarter,
        "Discriminatory Power Score",
    )
    fig.update_layout(xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"))
    return fig


# ---------------------------------------------------------------------------
# EAD RAG trend / metric trend charts
# ---------------------------------------------------------------------------


def build_ead_calibration_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    fig = build_lgd_calibration_rag_trend_figure(rag_trend, monitoring_quarter, range_value)
    quarters = [row["quarter"] for row in rag_trend if row["quarter"] in (filter_pd_periods_by_range(range_value, [r["quarter"] for r in rag_trend]))]
    fig.update_layout(xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"))
    return fig


def build_ead_discrimination_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    fig = build_lgd_discrimination_rag_trend_figure(rag_trend, monitoring_quarter, range_value)
    quarters = [row["quarter"] for row in rag_trend if row["quarter"] in (filter_pd_periods_by_range(range_value, [r["quarter"] for r in rag_trend]))]
    fig.update_layout(xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"))
    return fig


def build_lgd_metric_trend_figure(metric_rows, monitoring_thresholds, metric: str, monitoring_point: str) -> go.Figure:
    if not metric_rows:
        return _empty_figure("No LGD monitoring periods are available for the selected filters.", height=308)

    quarters = [row["Monitoring Period"] for row in metric_rows]
    values = [row.get(metric) for row in metric_rows]
    thresholds = _lgd_thresholds(monitoring_thresholds)
    threshold = next((row for row in thresholds if row.get("metric") == metric), {})
    rags = [calculate_pd_metric_rag(thresholds, metric, value) for value in values]
    bands = build_pd_threshold_bands(threshold, values)

    shapes = list(bands["shapes"])
    if monitoring_point in quarters:
        shapes.append(_vertical_marker(monitoring_point))

    display_name = "Mean Error" if metric == "ME" else metric
    hover_value_format = "%{y:.0%}" if metric in {"ME", "RMSE"} else "%{y:.3f}"
    tick_format = ".0%" if metric in {"ME", "RMSE"} else ".3f"
    fig = go.Figure(go.Scatter(
        x=quarters,
        y=values,
        mode="lines+markers",
        name=display_name,
        connectgaps=False,
        line=dict(color="rgba(71,85,105,0.75)", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in rags], line=dict(color="#fff", width=1)),
        customdata=rags,
        hovertemplate=f"%{{x}}<br>{display_name}: {hover_value_format}<br>RAG: %{{customdata}}<extra></extra>",
    ))
    fig.update_layout(
        height=308,
        margin=dict(t=18, r=26, b=54, l=64),
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"),
        yaxis=dict(title=display_name, tickformat=tick_format, range=bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
    )
    _apply_transparent_background(fig)
    return fig


def build_ead_metric_trend_figure(metric_rows, monitoring_thresholds, metric: str, monitoring_point: str) -> go.Figure:
    if not metric_rows:
        return _empty_figure("No EAD monitoring periods are available for the selected filters.", height=308)

    quarters = [row["Monitoring Period"] for row in metric_rows]
    values = [row.get(metric) for row in metric_rows]
    thresholds = _lgd_thresholds(monitoring_thresholds)
    threshold = next((row for row in thresholds if row.get("metric") == metric), {})
    rags = [calculate_pd_metric_rag(thresholds, metric, value) for value in values]
    bands = build_pd_threshold_bands(threshold, values)

    shapes = list(bands["shapes"])
    if monitoring_point in quarters:
        shapes.append(_vertical_marker(monitoring_point))

    display_name = "Mean Error" if metric == "ME" else metric
    hover_value_format = "%{y:.0%}" if metric in {"ME", "RMSE"} else "%{y:.3f}"
    tick_format = ".0%" if metric in {"ME", "RMSE"} else ".3f"
    fig = go.Figure(go.Scatter(
        x=quarters,
        y=values,
        mode="lines+markers",
        name=display_name,
        connectgaps=False,
        line=dict(color="rgba(71,85,105,0.75)", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in rags], line=dict(color="#fff", width=1)),
        customdata=rags,
        hovertemplate=f"%{{x}}<br>{display_name}: {hover_value_format}<br>RAG: %{{customdata}}<extra></extra>",
    ))
    fig.update_layout(
        height=308,
        margin=dict(t=18, r=26, b=54, l=64),
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"),
        yaxis=dict(title=display_name, tickformat=tick_format, range=bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
    )
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# Loss Performance charts
# ---------------------------------------------------------------------------


def _loss_thresholds(monitoring_thresholds) -> list[dict]:
    return list((monitoring_thresholds or {}).get("loss_thresholds") or [])


def build_loss_rag_trend_figure(rag_trend, monitoring_quarter, range_value=None) -> go.Figure:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in rag_trend])
    trend = [row for row in rag_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No Loss RAG periods are available for the selected monitoring point.")

    def pct(value):
        return "—" if value is None or not _finite(value) else f"{value * 100:.2f}%"

    quarters = [row["quarter"] for row in trend]
    customdata = [
        [
            row["rag"],
            pct(row.get("me_pct")),
            row.get("me_pct_rag") or "N/A",
            _format_metric_value(row.get("weighted_average"), 2),
            "—" if row.get("rounded_score") is None or not _finite(row.get("rounded_score")) else f"{row['rounded_score']}",
        ]
        for row in trend
    ]
    fig = _rag_dot_figure(
        quarters,
        [row["rag_score"] for row in trend],
        [row["rag"] for row in trend],
        customdata,
        "%{x}<br>Performance RAG: %{customdata[0]}<br>"
        "Mean Error % 1 year: %{customdata[1]} (%{customdata[2]})<br>"
        "Score: %{customdata[3]}<br>Rounded score: %{customdata[4]}<extra></extra>",
        monitoring_quarter,
        "Performance Score",
    )
    fig.update_layout(xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"))
    return fig


def build_loss_metric_trend_figure(metric_rows, monitoring_thresholds, monitoring_point: str) -> go.Figure:
    if not metric_rows:
        return _empty_figure("No Loss monitoring periods are available for the selected filters.", height=308)

    metric = "ME %"
    quarters = [row["Monitoring Period"] for row in metric_rows]
    values = [row.get(metric) for row in metric_rows]
    thresholds = _loss_thresholds(monitoring_thresholds)
    threshold = next((row for row in thresholds if row.get("metric") == metric), {})
    rags = [calculate_pd_metric_rag(thresholds, metric, value) for value in values]
    bands = build_pd_threshold_bands(threshold, values)

    shapes = list(bands["shapes"])
    if monitoring_point in quarters:
        shapes.append(_vertical_marker(monitoring_point))

    fig = go.Figure(go.Scatter(
        x=quarters,
        y=values,
        mode="lines+markers",
        name=metric,
        connectgaps=False,
        line=dict(color="rgba(71,85,105,0.75)", width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in rags], line=dict(color="#fff", width=1)),
        customdata=rags,
        hovertemplate="%{x}<br>Mean Error %: %{y:.0%}<br>RAG: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=308,
        margin=dict(t=18, r=26, b=54, l=64),
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="tight"),
        yaxis=dict(title="Mean Error", tickformat=".0%", range=bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
    )
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 1.2 / 1.4 Calibration Conservatism - Notching Trend (drawPdNotchingTrend)
# ---------------------------------------------------------------------------


def build_pd_notching_trend_figure(performance_trend, monitoring_thresholds, range_value=None, *, theme: str = "light") -> go.Figure:
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
    difference_axis_max = max(difference_bands["axis_range"][1], 0.5)
    notching_grid_color = "rgba(148,163,184,0.18)"
    notching_grid_width = 0.8
    trend_line_color = _monitoring_trend_line_color(theme)

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
        line=dict(color=trend_line_color, width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in difference_rags], line=dict(color="#fff", width=1)),
        customdata=difference_rags,
        hovertemplate="%{x}<br>Notching Difference: %{y:.0f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in difference_bands["shapes"]]
    green_min = threshold.get("green_min")
    green_max = threshold.get("green_max")
    amber_max = threshold.get("amber_max")
    if (
        threshold.get("red_condition") == "above amber_max"
        and _finite(green_min)
        and _finite(green_max)
        and green_min == 0
        and green_max == 0
        and _finite(amber_max)
    ):
        green_display_max = green_max + 0.05
        amber_display_max = amber_max + 0.05
        shapes = [
            {
                "type": "rect", "xref": "x2 domain", "x0": 0, "x1": 1, "yref": "y2",
                "y0": -0.5, "y1": green_display_max, "fillcolor": "rgba(22,163,74,.10)", "line": {"width": 0}, "layer": "below",
            },
            {
                "type": "rect", "xref": "x2 domain", "x0": 0, "x1": 1, "yref": "y2",
                "y0": green_display_max, "y1": amber_display_max, "fillcolor": "rgba(217,119,6,.18)", "line": {"width": 0}, "layer": "below",
            },
            {
                "type": "rect", "xref": "x2 domain", "x0": 0, "x1": 1, "yref": "y2",
                "y0": amber_display_max, "y1": difference_axis_max, "fillcolor": "rgba(220,38,38,.08)", "line": {"width": 0}, "layer": "below",
            },
        ]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend(trend_line_color, "Notching Difference", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    axis_kwargs = {"title": "Quarter", "gridcolor": notching_grid_color, "gridwidth": notching_grid_width}
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, axis_kwargs, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="CRR Notch", tickmode="linear", dtick=1, range=[0.5, 9.5], gridcolor=notching_grid_color, gridwidth=notching_grid_width, zeroline=False, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="Notching Difference", standoff=8), range=[-0.5, difference_axis_max], tickmode="linear", dtick=1, gridcolor=notching_grid_color, gridwidth=notching_grid_width, zeroline=False, automargin=True), row=1, col=2)
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 1.2 / 1.4 Calibration Conservatism - Confidence Interval Trend
# (drawPdConfidenceIntervalTrend)
# ---------------------------------------------------------------------------


def build_pd_confidence_interval_trend_figure(performance_trend, monitoring_thresholds, snapshot_quarter, range_value=None, *, theme: str = "light") -> go.Figure:
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
    trend_line_color = _monitoring_trend_line_color(theme)

    shapes = list(confidence_bands["shapes"])
    if snapshot_quarter in quarters:
        shapes.append(_vertical_marker(snapshot_quarter))

    fig = go.Figure(go.Scatter(
        x=quarters, y=confidence_values,
        mode="lines+markers", name="Confidence Interval Test",
        line=dict(color=trend_line_color, width=2.5),
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
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="compact"),
        yaxis=dict(title="Confidence Interval Test", tickformat=".0%", range=confidence_bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
    )
    _apply_transparent_background(fig)
    return fig


def build_pd_psi_trend_figure(performance_trend, monitoring_thresholds, snapshot_quarter, range_value=None, *, theme: str = "light") -> go.Figure:
    """Population Stability Index trend with threshold bands and RAG markers."""
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        return _empty_figure("No PSI periods are available for the selected monitoring point.")

    quarters = [row["quarter"] for row in trend]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    metric_name = get_pd_threshold_metric_name("Population Stability Index")
    threshold = next((row for row in thresholds if row.get("metric") == metric_name), {})
    psi_values = [row.get("population_stability_index") for row in trend]
    psi_rags = [calculate_pd_metric_rag(thresholds, "Population Stability Index", value) for value in psi_values]
    bands = build_pd_threshold_bands(threshold, psi_values, {"min_axis_max": 0.25})
    trend_line_color = _monitoring_trend_line_color(theme)

    shapes = list(bands["shapes"])
    if snapshot_quarter in quarters:
        shapes.append(_vertical_marker(snapshot_quarter))

    fig = go.Figure(go.Scatter(
        x=quarters, y=psi_values,
        mode="lines+markers", name="Population Stability Index",
        line=dict(color=trend_line_color, width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in psi_rags], line=dict(color="#fff", width=1)),
        customdata=psi_rags,
        hovertemplate="%{x}<br>PSI: %{y:.3f}<br>RAG: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=340,
        margin=dict(t=18, r=30, b=52, l=68),
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="compact"),
        yaxis=dict(title="Population Stability Index", tickformat=".3f", range=bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
    )
    _apply_transparent_background(fig)
    return fig


def build_pd_transition_combined_figure(rows, range_value=None, monitoring_thresholds=None, *, theme: str = "light") -> go.Figure:
    """Combined transition margin figure: levels (left) + delta bars (right).

    Left panel shows MM_P0 (dashed anchor) and MM_Pm (solid migration path).
    Right panel shows the delta (MM_Pm − MM_P0) as RAG-colored bars (against the
    ``Transition Matrix`` threshold). Both panels share the same x-axis labels so
    they read as a single visual unit.
    """
    all_rows = [row for row in (rows or []) if _finite(row.get("delta"))]
    if not all_rows:
        return _empty_figure("No transition-matrix margin data is available for the selected filters.", height=340, theme=theme)

    all_labels = [row.get("label") or f"Q{row.get('offset')}" for row in all_rows]
    filtered_labels = filter_pd_periods_by_range(range_value, all_labels)
    scoped = [row for row in all_rows if (row.get("label") or f"Q{row.get('offset')}") in filtered_labels]
    if not scoped:
        return _empty_figure("No data in the selected range.", height=340, theme=theme)

    labels = [row.get("label") or f"Q{row.get('offset')}" for row in scoped]
    periods = [row.get("period") or "" for row in scoped]
    p0_values = [row.get("mm_p0") for row in scoped]
    pm_values = [row.get("mm_pm") for row in scoped]
    deltas = [float(row["delta"]) for row in scoped]
    pm_color = _monitoring_trend_line_color(theme)

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.10,
        column_widths=[0.55, 0.45],
    )

    fig.add_trace(go.Scatter(
        x=labels, y=p0_values, mode="lines+markers", name="MM_P0 (anchor)",
        line=dict(color="#94a3b8", width=2, dash="dash"),
        marker=dict(size=7, color="#94a3b8", line=dict(color="#fff", width=1)),
        customdata=periods,
        hovertemplate="%{customdata}<br>MM_P0: %{y:.3%}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=labels, y=pm_values, mode="lines+markers", name="MM_Pm (migrated)",
        line=dict(color=pm_color, width=2.5),
        marker=dict(size=8, color=pm_color, line=dict(color="#fff", width=1)),
        customdata=periods,
        hovertemplate="%{customdata}<br>MM_Pm: %{y:.3%}<extra></extra>",
    ), row=1, col=1)

    thresholds = get_pd_thresholds(monitoring_thresholds) if monitoring_thresholds else []
    delta_rags = [calculate_pd_metric_rag(thresholds, "Transition Matrix", value) for value in deltas]
    bar_colors = [pd_rag_color(rag) for rag in delta_rags]
    fig.add_trace(go.Bar(
        x=labels, y=deltas, name="Delta",
        marker=dict(color=bar_colors, line=dict(color="rgba(255,255,255,0.6)", width=0.5)),
        customdata=[[period, p0, pm, rag] for period, p0, pm, rag in zip(periods, p0_values, pm_values, delta_rags)],
        hovertemplate="%{customdata[0]}<br>Delta: %{y:.3%}<br>MM_P0: %{customdata[1]:.3%}<br>MM_Pm: %{customdata[2]:.3%}<br>RAG: %{customdata[3]}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)

    fig.add_shape(
        type="line", xref="x2 domain", yref="y2",
        x0=0, x1=1, y0=0, y1=0,
        line=dict(color="#94a3b8", width=1, dash="dot"),
    )

    grid = "#94a3b8"
    xaxis_opts = build_pd_time_series_xaxis(labels, {"title": "Quarter", "gridcolor": grid}, density="compact")
    fig.update_xaxes(**xaxis_opts, row=1, col=1)
    fig.update_xaxes(**xaxis_opts, row=1, col=2)
    fig.update_yaxes(title_text="PD", tickformat=".2%", gridcolor=grid, zeroline=False, row=1, col=1)
    fig.update_yaxes(title_text="Delta", tickformat=".2%", gridcolor=grid, zeroline=False, row=1, col=2)

    fig.update_layout(
        height=360,
        margin=dict(t=32, r=30, b=52, l=68),
        hovermode="x unified",
        bargap=0.35,
        legend=dict(orientation="h", x=0, y=1.06),
    )
    for annotation in fig.layout.annotations:
        annotation.update(font=dict(size=12, color="#64748b"), x=annotation.x, xanchor="center")
    _apply_transparent_background(fig)
    return fig


def build_pd_sensitivity_combined_figure(rows, threshold: float | None, range_value=None, *, theme: str = "light") -> go.Figure:
    """Sensitivity: projected PD paths (left) + relative shock impact bars (right).

    Both panels share the same quarter offsets and can be windowed with the
    range controls. The impact bars keep their RAG colouring (within / above the
    scenario-test threshold) but no threshold reference line is drawn.
    """
    palette = _saas_theme_palette(_normalize_saas_theme(theme))
    scenario_order = ["baseline", "baseline_2std_shock"]
    scenario_styles = {
        "baseline": {"color": "#16a34a", "dash": "solid"},
        "baseline_2std_shock": {"color": "#dc2626", "dash": "dash"},
    }
    scoped_rows = [
        row for row in (rows or [])
        if row.get("scenario_variant") in scenario_order and _finite(row.get("projected_pd"))
    ]
    if not scoped_rows:
        return _empty_figure("No sensitivity projection data is available for the selected filters.", height=360, theme=theme)

    all_quarters = sorted({int(r["quarter"]) for r in scoped_rows if r.get("quarter") is not None})
    all_labels = [f"Q{q}" for q in all_quarters]
    kept_labels = set(filter_pd_periods_by_range(range_value, all_labels))
    quarters = [q for q in all_quarters if f"Q{q}" in kept_labels]
    if not quarters:
        return _empty_figure("No data in the selected range.", height=360, theme=theme)
    quarter_set = set(quarters)
    scoped_rows = [r for r in scoped_rows if int(r.get("quarter")) in quarter_set]

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.10,
        column_widths=[0.55, 0.45],
    )

    # --- Left: baseline vs shocked PD paths ---
    for scenario in scenario_order:
        scenario_rows = sorted(
            [r for r in scoped_rows if r.get("scenario_variant") == scenario],
            key=lambda r: r.get("quarter", 0),
        )
        if not scenario_rows:
            continue
        style = scenario_styles[scenario]
        fig.add_trace(go.Scatter(
            x=[r.get("quarter") for r in scenario_rows],
            y=[r.get("projected_pd") for r in scenario_rows],
            mode="lines+markers", name=scenario,
            line=dict(color=style["color"], width=2.7, dash=style["dash"]),
            marker=dict(size=7, line=dict(color="#fff", width=1)),
            customdata=[[_format_saas_quarter_label(_coerce_saas_date(r.get("projection_quarter")))] for r in scenario_rows],
            hovertemplate="%{customdata[0]}<br>%{fullData.name}: %{y:.2%}<extra></extra>",
        ), row=1, col=1)

    # --- Right: relative shock impact bars (RAG-coloured, no threshold line) ---
    baseline_by_offset = {
        r.get("quarter"): r for r in scoped_rows
        if r.get("scenario_variant") == "baseline" and _finite(r.get("projected_pd"))
    }
    points = []
    for r in scoped_rows:
        if r.get("scenario_variant") != "baseline_2std_shock" or not _finite(r.get("projected_pd")):
            continue
        base = baseline_by_offset.get(r.get("quarter"))
        base_val = base.get("projected_pd") if base else None
        if not _finite(base_val) or float(base_val) <= 0:
            continue
        impact = abs(float(r["projected_pd"]) - float(base_val)) / float(base_val)
        rag = "Green" if threshold is not None and impact <= threshold else ("Red" if threshold is not None else "N/A")
        points.append({
            "q": int(r["quarter"]),
            "period": _format_saas_quarter_label(_coerce_saas_date(r.get("projection_quarter"))),
            "baseline": float(base_val), "shocked": float(r["projected_pd"]), "impact": impact, "rag": rag,
        })
    points.sort(key=lambda p: p["q"])
    if points:
        colors = ["rgba(22,163,74,0.78)" if p["rag"] == "Green" else "rgba(220,38,38,0.80)" for p in points]
        fig.add_trace(go.Bar(
            x=[p["q"] for p in points], y=[p["impact"] for p in points], name="Relative shock impact",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.75)", width=1)),
            customdata=[[p["period"], p["baseline"], p["shocked"], p["rag"]] for p in points],
            hovertemplate="%{customdata[0]}<br>Impact: %{y:.1%}<br>Baseline PD: %{customdata[1]:.2%}<br>Shocked PD: %{customdata[2]:.2%}<br>RAG: %{customdata[3]}<extra></extra>",
            showlegend=False,
        ), row=1, col=2)

    tickvals = quarters
    ticktext = [f"Q{q}" for q in quarters]
    axis_kw = dict(tickmode="array", tickvals=tickvals, ticktext=ticktext, tickangle=0,
                   tickfont=dict(size=11, color=palette["axis_tick"]), gridcolor=palette["grid_color"],
                   linecolor=palette["axis_line"], showline=True, ticks="outside", automargin=True,
                   title=dict(text="Quarter", font=dict(size=12, color=palette["axis_title"])))
    fig.update_xaxes(**axis_kw, row=1, col=1)
    fig.update_xaxes(**axis_kw, row=1, col=2)
    fig.update_yaxes(title_text="Projected PD", tickformat=".1%", gridcolor=palette["grid_color"], zeroline=False, rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Relative Shock Impact", tickformat=".0%", gridcolor=palette["grid_color"], zeroline=False, rangemode="tozero", row=1, col=2)

    fig.update_layout(
        height=360,
        margin=dict(t=32, r=30, b=60, l=70),
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.08),
    )
    for annotation in fig.layout.annotations:
        annotation.update(font=dict(size=12, color="#64748b"), xanchor="center")
    _apply_transparent_background(fig)
    return fig


def build_pd_scenario_projection_figure(rows, *, theme: str = "light") -> go.Figure:
    """Projected PD paths for every available scenario variant."""
    normalized_theme = _normalize_saas_theme(theme)
    palette = _saas_theme_palette(normalized_theme)
    scenario_color_map = SAAS_DARK_SCENARIO_COLOR_MAP if normalized_theme == "dark" else SAAS_SCENARIO_COLOR_MAP
    fallback_colors = SAAS_DARK_SCENARIO_FALLBACK_COLORS if normalized_theme == "dark" else SAAS_SCENARIO_FALLBACK_COLORS
    scoped_rows = [row for row in (rows or []) if _finite(row.get("projected_pd")) and row.get("scenario_variant")]
    if not scoped_rows:
        return _empty_figure("No scenario projection data is available for the selected filters.", height=360, theme=theme)

    quarters = sorted({
        int(row.get("quarter"))
        for row in scoped_rows
        if row.get("quarter") is not None
    })
    scenarios = sorted(
        {str(row.get("scenario_variant")) for row in scoped_rows},
        key=lambda scenario: (SAAS_SCENARIO_ORDER.get(str(scenario).lower(), 99), str(scenario)),
    )
    y_values = [float(row["projected_pd"]) for row in scoped_rows]
    y_max = max(y_values) * 1.16 if y_values else 0.05
    assigned_colors: dict[str, str] = {}

    fig = go.Figure()
    for scenario in scenarios:
        scenario_rows = sorted(
            [row for row in scoped_rows if row.get("scenario_variant") == scenario],
            key=lambda row: row.get("quarter", 0),
        )
        x_values = [row.get("quarter") for row in scenario_rows]
        y_values = [row.get("projected_pd") for row in scenario_rows]
        customdata = [
            [f"Q{row.get('quarter')}", _format_saas_quarter_label(_coerce_saas_date(row.get("projection_quarter")))]
            for row in scenario_rows
        ]
        color = _saas_scenario_color(
            scenario,
            assigned_colors,
            base_colors=scenario_color_map,
            fallback_colors=fallback_colors,
        )
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines+markers",
            name=str(scenario),
            line=dict(color=color, width=2.6),
            marker=dict(size=7, line=dict(color="#fff", width=1)),
            customdata=customdata,
            hovertemplate="%{customdata[1]}<br>%{fullData.name}: %{y:.2%}<br>Quarter: %{customdata[0]}<extra></extra>",
        ))

    fig.update_layout(
        height=360,
        margin=dict(t=22, r=34, b=64, l=70),
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.12),
        showlegend=True,
        xaxis=dict(
            title=dict(text="Quarter", font=dict(size=12, color=palette["axis_title"])),
            tickmode="array",
            tickvals=quarters,
            ticktext=[f"Q{quarter}" for quarter in quarters],
            tickangle=0,
            tickfont=dict(size=11, color=palette["axis_tick"]),
            gridcolor=palette["grid_color"],
            linecolor=palette["axis_line"],
            showline=True,
            ticks="outside",
            automargin=True,
        ),
        yaxis=dict(
            title="Projected PD",
            tickformat=".1%",
            range=[0, y_max],
            gridcolor=palette["grid_color"],
            zeroline=False,
            showline=True,
            linecolor=palette["axis_line"],
            automargin=True,
        ),
    )
    _apply_transparent_background(fig)
    return fig


def build_pd_scenario_rank_figure(rows, *, theme: str = "light") -> go.Figure:
    """Scenario rank matrix where rank 1 is the highest projected PD."""
    palette = _saas_theme_palette(_normalize_saas_theme(theme))
    scoped_rows = [row for row in (rows or []) if _finite(row.get("projected_pd")) and row.get("scenario_variant")]
    if not scoped_rows:
        return _empty_figure("No scenario ranking data is available for the selected filters.", height=330, theme=theme)

    quarters = sorted({
        int(row.get("quarter"))
        for row in scoped_rows
        if row.get("quarter") is not None
    })
    scenarios = sorted(
        {str(row.get("scenario_variant")) for row in scoped_rows},
        key=lambda scenario: (SAAS_SCENARIO_ORDER.get(str(scenario).lower(), 99), str(scenario)),
    )
    scenario_labels = [str(scenario) for scenario in scenarios]
    rows_by_quarter: dict[int, list[dict]] = {}
    for row in scoped_rows:
        rows_by_quarter.setdefault(int(row["quarter"]), []).append(row)

    z_values = []
    customdata = []
    text_values = []
    for scenario in scenarios:
        z_row = []
        custom_row = []
        text_row = []
        for quarter in quarters:
            quarter_rows = rows_by_quarter.get(quarter, [])
            ranked = sorted(quarter_rows, key=lambda item: float(item.get("projected_pd") or 0), reverse=True)
            n = len(ranked)
            rank_by_scenario = {item.get("scenario_variant"): n - rank for rank, item in enumerate(ranked)}
            value_by_scenario = {item.get("scenario_variant"): item.get("projected_pd") for item in ranked}
            rank = rank_by_scenario.get(scenario)
            projected_pd = value_by_scenario.get(scenario)
            z_row.append(rank)
            text_row.append(str(rank) if rank is not None else "")
            custom_row.append([
                f"Q{quarter}",
                str(scenario),
                projected_pd,
                rank,
            ])
        z_values.append(z_row)
        text_values.append(text_row)
        customdata.append(custom_row)

    fig = go.Figure(go.Heatmap(
        x=[f"Q{quarter}" for quarter in quarters],
        y=scenario_labels,
        z=z_values,
        text=text_values,
        texttemplate="%{text}",
        customdata=customdata,
        zmin=1,
        zmax=max(len(scenarios), 1),
        colorscale=[
            [0.0, "rgba(22,163,74,0.70)"],
            [0.5, "rgba(245,158,11,0.72)"],
            [1.0, "rgba(220,38,38,0.88)"],
        ],
        colorbar=dict(
            title="Rank",
            tickmode="array",
            tickvals=list(range(1, len(scenarios) + 1)),
            ticktext=[str(value) for value in range(1, len(scenarios) + 1)],
        ),
        hovertemplate=(
            "%{customdata[0]}<br>"
            "Scenario: %{customdata[1]}<br>"
            "Projected PD: %{customdata[2]:.2%}<br>"
            "Rank: %{customdata[3]} (highest = highest PD)<extra></extra>"
        ),
    ))
    fig.update_layout(
        height=330,
        margin=dict(t=22, r=68, b=58, l=128),
        xaxis=dict(
            title=dict(text="Quarter", font=dict(size=12, color=palette["axis_title"])),
            tickangle=0,
            tickfont=dict(size=11, color=palette["axis_tick"]),
            side="bottom",
        ),
        yaxis=dict(
            title="Scenario",
            tickfont=dict(size=11, color=palette["axis_tick"]),
        ),
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


def build_pd_discrimination_trend_figures(performance_trend, monitoring_thresholds, snapshot_quarter, range_value=None, *, theme: str = "light") -> dict[str, go.Figure]:
    periods = filter_pd_periods_by_range(range_value, [row["quarter"] for row in performance_trend])
    trend = [row for row in performance_trend if row["quarter"] in periods]
    if not trend:
        message = _empty_figure("No portfolio periods are available for the selected snapshot date.", height=296)
        return {metric["key"]: message for metric in _DISCRIMINATION_TREND_METRICS}

    quarters = [row["quarter"] for row in trend]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    figures: dict[str, go.Figure] = {}
    trend_line_color = _monitoring_trend_line_color(theme)
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
            line=dict(color=trend_line_color, width=2.5, dash=metric["dash"]),
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
            xaxis=build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": GRID_COLOR}, density="compact"),
            yaxis=dict(title=metric["name"], range=bands["axis_range"], gridcolor=GRID_COLOR, zeroline=False),
        )
        _apply_transparent_background(fig)
        figures[metric["key"]] = fig
    return figures


# ---------------------------------------------------------------------------
# 1.3 Discriminatory Power - Accuracy Ratio / Go-Live Delta Trend
# (drawPdGoLiveAccuracyTrend)
# ---------------------------------------------------------------------------


def build_pd_go_live_accuracy_trend_figure(performance_trend, monitoring_thresholds, go_live_quarter, range_value=None, *, theme: str = "light") -> go.Figure:
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
    delta_grid_color = "rgba(148,163,184,0.18)"
    delta_grid_width = 0.8
    trend_line_color = _monitoring_trend_line_color(theme)

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
        line=dict(color=trend_line_color, width=2.5),
        marker=dict(size=8, color=[pd_rag_color(rag) for rag in delta_rags], line=dict(color="#fff", width=1)),
        customdata=delta_rags,
        hovertemplate="%{x}<br>Delta Accuracy Ratio: %{y:.3f}<br>RAG: %{customdata}<extra></extra>",
    ), row=1, col=2)

    shapes = [{**shape, "xref": "x2 domain", "yref": "y2"} for shape in delta_bands["shapes"]]
    shapes.append(_vertical_marker(last_quarter, xref="x", yref="y domain"))
    shapes.append(_vertical_marker(last_quarter, xref="x2", yref="y2 domain"))
    legend_shapes, legend_annotations = _dual_panel_legend(trend_line_color, "Delta Accuracy Ratio", _DUAL_PANEL_SECONDARY_DOMAIN)
    shapes.extend(legend_shapes)

    fig.update_layout(
        height=330,
        margin=dict(t=34, r=48, b=82, l=72),
        hovermode="closest",
        legend=dict(orientation="h", x=0, y=1.22),
        annotations=legend_annotations,
        shapes=shapes,
    )
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, {"title": "Quarter", "gridcolor": delta_grid_color, "gridwidth": delta_grid_width}, density="compact"), row=1, col=1)
    fig.update_xaxes(build_pd_time_series_xaxis(quarters, {"title": f"Portfolio Quarter (from {go_live_quarter})", "gridcolor": delta_grid_color, "gridwidth": delta_grid_width}, density="compact"), row=1, col=2)
    fig.update_yaxes(dict(title="Accuracy Ratio", gridcolor=delta_grid_color, gridwidth=delta_grid_width, zeroline=False, automargin=True), row=1, col=1)
    fig.update_yaxes(dict(title=dict(text="Delta Accuracy Ratio", standoff=8), range=delta_bands["axis_range"], gridcolor=delta_grid_color, gridwidth=delta_grid_width, zeroline=False, automargin=True), row=1, col=2)
    _apply_transparent_background(fig)
    return fig


# ---------------------------------------------------------------------------
# 2.6 MEV Range (drawPdMevRangeChart)
# ---------------------------------------------------------------------------


def _pd_quarter_to_date(quarter_label: str):
    """Convert a ``YYYY-Qn`` quarter label to the quarter-end ``date``."""
    match = re.match(r"^(\d{4})-Q([1-4])$", quarter_label or "")
    if not match:
        return None
    year, q = int(match.group(1)), int(match.group(2))
    end_month = q * 3
    last_day = calendar.monthrange(year, end_month)[1]
    return date(year, end_month, last_day)


def _format_pd_mev_quarter_tick(quarter_label: str) -> str:
    """Format a ``YYYY-Qn`` quarter label as ``YYYYQn`` (matching the SAAS axis style)."""
    match = re.match(r"^(\d{4})-Q([1-4])$", quarter_label or "")
    if not match:
        return quarter_label or ""
    return f"{match.group(1)}Q{match.group(2)}"


def build_pd_mev_range_figure(model_data, mev_name: str, mev_data, color: str, range_value=None, *, current_quarter: str | None = None, theme: str = "light", reporting_cycle: str | None = None, scenario: str | None = None) -> go.Figure:
    palette = _saas_theme_palette(_normalize_saas_theme(theme))
    selected_scenario = str(scenario or "baseline").strip()
    scenario_data = get_pd_mev_scenario_series(mev_data, reporting_cycle, selected_scenario)
    ts = scenario_data if scenario_data else (mev_data.get("time_series") or {})
    all_points = sorted(
        ((quarter, value) for quarter, value in ts.items() if _finite(value)),
        key=lambda item: _pd_quarter_sort_key(item[0]),
    )
    visible_quarters = set(filter_pd_periods_by_range(range_value, [point[0] for point in all_points]))
    points = [point for point in all_points if point[0] in visible_quarters]
    if not points:
        return _empty_figure("No MEV time-series data is available for the selected time window.", height=292, theme=theme)

    thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
    quarters = [point[0] for point in points]
    values = [point[1] for point in points]
    raw_dev_date = (mev_data.get("dev_range") or {}).get("development_date") or ""
    development_quarter = raw_dev_date if re.match(r"^\d{4}-Q[1-4]$", raw_dev_date) else iso_date_to_pd_quarter(raw_dev_date)
    severe_quarter = iso_date_to_pd_quarter(model_data.get("severe_scenario_date"))
    scenario_marker_quarter = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, selected_scenario) or current_quarter

    quarter_dates = [_pd_quarter_to_date(q) for q in quarters]
    quarter_date_map = dict(zip(quarters, quarter_dates))

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
        shapes.extend([
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=y_min, y1=amber_lower, fillcolor="rgba(239,68,68,0.10)", line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=amber_lower, y1=green_min, fillcolor="rgba(245,158,11,0.12)", line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_min, y1=green_max, fillcolor="rgba(34,197,94,0.12)", line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_max, y1=amber_upper, fillcolor="rgba(245,158,11,0.12)", line=dict(width=0), layer="below"),
            dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=amber_upper, y1=y_max, fillcolor="rgba(239,68,68,0.10)", line=dict(width=0), layer="below"),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_min, y1=green_min, line=dict(color="#f59e0b", width=1.3, dash="dash")),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_max, y1=green_max, line=dict(color="#f59e0b", width=1.3, dash="dash")),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=amber_lower, y1=amber_lower, line=dict(color="#ef4444", width=1, dash="dot")),
            dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=amber_upper, y1=amber_upper, line=dict(color="#ef4444", width=1, dash="dot")),
        ])

    dev_date = quarter_date_map.get(development_quarter)
    if dev_date is not None:
        shapes.append(_vertical_marker(dev_date, color=palette["development_marker"], dash="dot", width=1.8))
    severe_date = quarter_date_map.get(severe_quarter)
    if severe_date is not None:
        shapes.append(_vertical_marker(severe_date, color="#9a3412", dash="dash"))
    scenario_marker_date = quarter_date_map.get(scenario_marker_quarter)
    if scenario_marker_date is not None:
        shapes.append(_vertical_marker(scenario_marker_date, color=palette["scenario_date_marker"], dash="dash", width=1.8))

    fig = go.Figure()
    has_split = scenario_marker_quarter and scenario_marker_quarter in quarters
    if has_split:
        split_index = quarters.index(scenario_marker_quarter)
        history_dates = quarter_dates[: split_index + 1]
        history_values = values[: split_index + 1]
        history_labels = quarters[: split_index + 1]
        future_dates = quarter_dates[split_index:]
        future_values = values[split_index:]
        future_labels = quarters[split_index:]
        fig.add_trace(go.Scatter(
            x=history_dates, y=history_values,
            mode="lines", connectgaps=False,
            line=dict(color=color, width=2.6, shape="spline", smoothing=0.45),
            customdata=[_format_pd_mev_quarter_tick(q) for q in history_labels],
            hovertemplate=f"%{{customdata}}<br>{mev_name}: %{{y:,.2f}}<extra></extra>",
            showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=future_dates, y=future_values,
            mode="lines", connectgaps=False,
            line=dict(color=color, width=2.6, shape="spline", smoothing=0.45),
            opacity=0.35,
            customdata=[_format_pd_mev_quarter_tick(q) for q in future_labels],
            hovertemplate=f"%{{customdata}}<br>{mev_name}: %{{y:,.2f}}<extra></extra>",
            showlegend=False,
        ))
    else:
        fig.add_trace(go.Scatter(
            x=quarter_dates, y=values,
            mode="lines", connectgaps=False,
            line=dict(color=color, width=2.6, shape="spline", smoothing=0.45),
            customdata=[_format_pd_mev_quarter_tick(q) for q in quarters],
            hovertemplate=f"%{{customdata}}<br>{mev_name}: %{{y:,.2f}}<extra></extra>",
            showlegend=False,
        ))

    threshold_annotations = []
    if thresholds:
        threshold_labels = [
            (thresholds["amber_upper"], "Max_Dev + 2 SD"),
            (thresholds["green_max"], "Max_Dev"),
            (thresholds["green_min"], "Min_Dev"),
            (thresholds["amber_lower"], "Min_Dev − 2 SD"),
        ]
        for y_val, label in threshold_labels:
            threshold_annotations.append(dict(
                xref="paper", x=1.01, yref="y", y=y_val,
                text=label, showarrow=False, xanchor="left", yanchor="middle",
                font=dict(size=9, color="#64748b"),
            ))

    tickvals = _build_saas_date_ticks(quarter_dates, max_ticks=5)
    ticktext = [_format_saas_quarter_label(d) for d in tickvals]
    fig.update_layout(
        height=292,
        margin=dict(t=16, r=100, b=72, l=58),
        annotations=threshold_annotations,
        hovermode="x unified",
        showlegend=False,
        shapes=shapes,
        xaxis=dict(
            title=dict(text="Quarter", font=dict(size=12, color=palette["axis_title"])),
            type="date",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont=dict(size=11, color=palette["axis_tick"]),
            gridcolor=palette["grid_color"],
            gridwidth=1,
            showline=True,
            linecolor=palette["axis_line"],
            ticks="outside",
            tickangle=0,
            automargin=True,
            showspikes=True,
            spikecolor=palette["spike_color"],
            spikedash="dot",
            spikemode="across",
            spikethickness=1,
        ),
        yaxis=dict(title=mev_name, range=[y_min, y_max], automargin=True, gridcolor=palette["grid_color"], zerolinecolor=palette["zero_line"], showline=True, linecolor=palette["axis_line"], ticks="outside"),
    )
    _apply_transparent_background(fig)
    return fig


def _saas_quarter_zero_date(records) -> object | None:
    quarter_zero_dates = [
        row.get("Date")
        for row in records or []
        if _finite(row.get("Quarter")) and float(row.get("Quarter")) == 0 and row.get("Date") is not None
    ]
    return min(quarter_zero_dates) if quarter_zero_dates else None


def _saas_add_months(date_value, months: int):
    if date_value is None:
        return None
    total_month = date_value.month - 1 + months
    year = date_value.year + total_month // 12
    month = total_month % 12 + 1
    day = min(date_value.day, calendar.monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def _saas_projection_x_date(projection_start_date, quarter_value):
    """Map a projection Quarter offset onto the primary Reporting Cycle's date axis."""
    if projection_start_date is None or quarter_value is None:
        return None
    return _saas_add_months(projection_start_date, round(quarter_value * 3))


def _saas_historical_values(records) -> list[float]:
    return [
        float(row.get("MEV Value"))
        for row in records or []
        if _finite(row.get("MEV Value")) and _finite(row.get("Quarter")) and float(row.get("Quarter")) <= 0
    ]


def _saas_filter_primary_run_for(records, primary_run_for: str | None):
    if not primary_run_for:
        return list(records or [])
    return [
        row
        for row in records or []
        if str(row.get("Run For") or "").strip() == primary_run_for
    ]


def compute_saas_monitoring_band_spec(records, *, primary_run_for: str | None = None, development_date=None):
    monitoring_records = _saas_filter_primary_run_for(records, primary_run_for)
    development_reference_values = [
        float(row.get("MEV Value"))
        for row in monitoring_records
        if _finite(row.get("MEV Value"))
        and _finite(row.get("Quarter"))
        and float(row.get("Quarter")) <= 0
        and development_date is not None
        and row.get("Date") is not None
        and row.get("Date") <= development_date
    ]
    if not development_reference_values:
        return None

    dev_min = min(development_reference_values)
    dev_max = max(development_reference_values)
    dev_std = statistics.pstdev(development_reference_values) if len(development_reference_values) > 1 else 0.0
    lower_yellow = dev_min - (2 * dev_std)
    upper_yellow = dev_max + (2 * dev_std)
    return {
        "green_low": dev_min,
        "green_high": dev_max,
        "amber_low_low": lower_yellow,
        "amber_low_high": dev_min,
        "amber_high_low": dev_max,
        "amber_high_high": upper_yellow,
        "red_low_cutoff": lower_yellow,
        "red_high_cutoff": upper_yellow,
    }


def build_saas_mev_time_series_figure(
    records,
    mev_label_map=None,
    model_label_map=None,
    y_axis_title: str | None = None,
    snapshot_period: str = "history_projection",
    historical_reference_records=None,
    monitoring_reference_records=None,
    reference_lines: str = "none",
    empty_message: str = "No MEV time-series data matches the current SAAS filters.",
    primary_run_for: str | None = None,
    development_date=None,
    current_date=None,
    projection_start_date=None,
    theme: str = "light",
) -> go.Figure:
    """Plot quarterly MEV time series for the selected SAAS model(s)."""
    normalized_theme = _normalize_saas_theme(theme)
    palette = _saas_theme_palette(normalized_theme)
    scenario_color_map = SAAS_DARK_SCENARIO_COLOR_MAP if normalized_theme == "dark" else SAAS_SCENARIO_COLOR_MAP
    scenario_fallback_colors = SAAS_DARK_SCENARIO_FALLBACK_COLORS if normalized_theme == "dark" else SAAS_SCENARIO_FALLBACK_COLORS
    mev_label_map = mev_label_map or {}
    model_label_map = model_label_map or {}
    resolved_y_axis_title = str(y_axis_title or "").strip() or "MEV Value"
    is_history_only = snapshot_period == "history"
    is_projection_only = snapshot_period == "projection"
    if projection_start_date is None:
        projection_start_date = _saas_quarter_zero_date(records)

    grouped: dict[tuple[str, str, str, str], list[tuple[object, float | None, float]]] = {}
    selected_models: set[str] = set()
    selected_run_fors: set[str] = set()
    visible_values: list[float] = []
    for row in records or []:
        model_name = str(row.get("Model Name") or "").strip()
        mev_name = str(row.get("MEV Name") or "").strip()
        scenario = str(row.get("Scenario") or "").strip().lower()
        run_for = str(row.get("Run For") or "").strip()
        date_value = row.get("Date")
        numeric_value = row.get("MEV Value")
        if not model_name or not mev_name or not run_for or date_value is None or not _finite(numeric_value):
            continue
        selected_models.add(model_name)
        selected_run_fors.add(run_for)
        float_value = float(numeric_value)
        visible_values.append(float_value)
        quarter_value = float(row.get("Quarter")) if _finite(row.get("Quarter")) else None
        grouped.setdefault((model_name, mev_name, scenario, run_for), []).append((date_value, quarter_value, float_value))

    if not grouped:
        return _empty_figure(empty_message, height=420, theme=theme)

    multiple_models = len(selected_models) > 1
    multiple_run_fors = len(selected_run_fors) > 1
    legend_item_count = len(grouped)
    compact_legend = legend_item_count >= 5
    ultra_compact_legend = legend_item_count >= 9
    scenario_colors: dict[str, str] = {}
    ordered_run_fors = sorted(selected_run_fors, key=lambda value: (value != (primary_run_for or ""), value))
    run_for_rank_map = {run_for: index for index, run_for in enumerate(ordered_run_fors)}
    run_for_dash_map = {
        run_for: SAAS_RUN_FOR_DASHES[min(index, len(SAAS_RUN_FOR_DASHES) - 1)]
        for index, run_for in enumerate(ordered_run_fors)
    }
    fig = go.Figure()
    all_axis_values = []

    def _is_historical_point(point):
        date_value, quarter_value, _ = point
        if quarter_value is not None and quarter_value > 0:
            return False
        if projection_start_date is not None and date_value > projection_start_date:
            return False
        return True

    ordered_group_keys = sorted(
        grouped,
        key=lambda item: (
            item[0],
            item[1],
            SAAS_SCENARIO_ORDER.get(str(item[2] or "").strip().lower(), 99),
            0 if primary_run_for and item[3] == primary_run_for else 1,
            item[3],
        ),
    )

    for model_name, mev_name, scenario, run_for in ordered_group_keys:
        color = _saas_scenario_color(
            scenario,
            scenario_colors,
            base_colors=scenario_color_map,
            fallback_colors=scenario_fallback_colors,
        )
        points = sorted(
            grouped[(model_name, mev_name, scenario, run_for)],
            key=lambda item: item[1] if is_projection_only and item[1] is not None else item[0],
        )
        is_primary_run_for = bool(primary_run_for and run_for == primary_run_for)
        run_for_dash = run_for_dash_map.get(run_for, "solid")
        if reference_lines in ("monitoring", "min_max", "none"):
            run_for_dash = "solid" if is_primary_run_for or not multiple_run_fors else "dash"
            if normalized_theme == "dark":
                color = "#86efac" if scenario == "baseline" else "#fb7185" if scenario == "intsevere" else "#d8e1ee"
            else:
                color = "#16a34a" if scenario == "baseline" else "#dc2626" if scenario == "intsevere" else "#0f172a"

        mev_label = mev_label_map.get(mev_name) or mev_name
        model_label = model_label_map.get(model_name) or model_name
        scenario_label = _format_saas_scenario_label(scenario)
        trace_name = _format_saas_legend_label(
            model_label=model_label,
            scenario_label=scenario_label,
            multiple_models=multiple_models,
            run_for=_compact_run_for_label(run_for) if ultra_compact_legend else run_for,
            multiple_run_fors=multiple_run_fors,
            compact=compact_legend,
        )
        legend_rank = (
            SAAS_SCENARIO_ORDER.get(str(scenario or "").strip().lower(), 99) * 10
            + run_for_rank_map.get(run_for, 9)
        )

        trace_mode = "lines+markers" if reference_lines == "monitoring" or is_history_only else "lines"
        marker_size = 5.8 if reference_lines == "monitoring" else (3.4 if is_history_only and is_primary_run_for else 2.9 if is_history_only else 0)
        marker_line_width = 1.6 if reference_lines == "monitoring" else (0.9 if is_history_only else 0)
        marker_fill_color = palette["marker_fill"] if reference_lines == "monitoring" or is_history_only else color
        hovertemplate = (
            f"Model: {model_label}<br>"
            f"Run For: {run_for}<br>"
            f"Scenario: {scenario_label}<br>"
            f"MEV: {mev_label}<br>"
            + ("Projection Quarter: %{x}<br>" if is_projection_only else "")
            + ("Calendar Quarter: %{customdata}<br>" if is_projection_only else "Quarter: %{customdata}<br>")
            + "Value: %{y:,.2f}<extra></extra>"
        )
        legend_group = f"{model_name}|{mev_name}|{scenario}|{run_for}"
        history_projection_mode = snapshot_period == "history_projection" and not is_projection_only and not is_history_only

        def add_trace(
            segment_points,
            *,
            line_color,
            marker_color,
            marker_border_color,
            opacity,
            showlegend,
            mode,
            line_width_override=None,
            hovertemplate_override=None,
            quarter_aligned=False,
            customdata_override=None,
        ):
            if not segment_points:
                return
            segment_dates = [point[0] for point in segment_points]
            segment_quarters = [point[1] for point in segment_points]
            if is_projection_only:
                segment_x_values = segment_quarters
            elif quarter_aligned and projection_start_date is not None:
                segment_x_values = [
                    _saas_projection_x_date(projection_start_date, quarter_value)
                    if quarter_value is not None
                    else date_value
                    for date_value, quarter_value in zip(segment_dates, segment_quarters)
                ]
            else:
                segment_x_values = segment_dates
            all_axis_values.extend(value for value in segment_x_values if value is not None)
            fig.add_trace(
                go.Scatter(
                    x=segment_x_values,
                    y=[point[2] for point in segment_points],
                    mode=mode,
                    name=trace_name,
                    legendgroup=legend_group,
                    legendrank=legend_rank,
                    line=dict(
                        color=line_color,
                        width=(
                            line_width_override
                            if line_width_override is not None
                            else 2.1 if is_primary_run_for and is_history_only else 1.7 if is_history_only else 2.35 if is_primary_run_for else 1.95
                        ),
                        dash=run_for_dash,
                        shape="linear",
                    ),
                    marker=dict(
                        size=marker_size,
                        color=marker_color,
                        line=dict(color=marker_border_color, width=marker_line_width),
                    ),
                    customdata=customdata_override
                    if customdata_override is not None
                    else [_format_saas_quarter_label(point_date) for point_date in segment_dates],
                    showlegend=showlegend,
                    opacity=opacity,
                    hovertemplate=hovertemplate_override or hovertemplate,
                )
            )

        if history_projection_mode:
            history_points = [point for point in points if _is_historical_point(point)]
            projection_points = [point for point in points if not _is_historical_point(point)]
            projection_trace_points = list(projection_points)
            if history_points and projection_points:
                projection_trace_points = [history_points[-1], *projection_points]

            add_trace(
                history_points,
                line_color=color,
                marker_color=marker_fill_color,
                marker_border_color=color,
                opacity=1 if is_primary_run_for or not multiple_run_fors else 0.92,
                showlegend=bool(history_points) or not projection_trace_points,
                mode="lines",
                line_width_override=2.2 if is_primary_run_for else 1.85,
                hovertemplate_override=hovertemplate.replace(
                    f"MEV: {mev_label}<br>",
                    f"MEV: {mev_label}<br>Segment: History<br>",
                ),
            )
            add_trace(
                projection_trace_points,
                line_color=color,
                marker_color=marker_fill_color,
                marker_border_color=color,
                opacity=0.35 if is_primary_run_for or not multiple_run_fors else 0.3,
                showlegend=not history_points,
                mode="lines",
                line_width_override=2.2 if is_primary_run_for else 1.85,
                hovertemplate_override=hovertemplate.replace(
                    f"MEV: {mev_label}<br>",
                    f"MEV: {mev_label}<br>Segment: Projection<br>",
                ),
                quarter_aligned=True,
                customdata_override=[_format_saas_quarter_value(point[1]) for point in projection_trace_points],
            )
        else:
            add_trace(
                points,
                line_color=color,
                marker_color=marker_fill_color,
                marker_border_color=color,
                opacity=1 if is_primary_run_for or not multiple_run_fors else 0.84 if is_history_only else 0.78,
                showlegend=True,
                mode=trace_mode,
            )

    legend_y = -0.38 if ultra_compact_legend else -0.22 if compact_legend else -0.21
    bottom_margin = 198 if ultra_compact_legend else 136 if compact_legend else 130

    shapes: list[dict] = [] if is_projection_only else _saas_history_year_band_shapes(
        all_axis_values,
        fillcolor=palette["year_band_fill"],
    )
    annotations: list[dict] = []
    min_max_reference_records = historical_reference_records if historical_reference_records is not None else records
    if primary_run_for:
        min_max_reference_records = [
            row
            for row in min_max_reference_records
            if str(row.get("Run For") or "").strip() == primary_run_for
        ]
    historical_reference_values = _saas_historical_values(min_max_reference_records)
    if (
        snapshot_period == "history_projection"
        and projection_start_date is not None
        and not (reference_lines == "monitoring" and current_date and projection_start_date == current_date)
    ):
        projection_end_date = None
        if all_axis_values:
            projection_end_date = max(value for value in all_axis_values if value is not None)
        if projection_end_date is not None and projection_end_date > projection_start_date:
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    x0=projection_start_date,
                    x1=projection_end_date,
                    yref="paper",
                    y0=0,
                    y1=1,
                    fillcolor=palette["projection_band_fill"],
                    line=dict(width=0),
                    layer="below",
                )
            )
        shapes.append(_vertical_marker(projection_start_date, xref="x", yref="paper", color=palette["projection_marker"], dash="dash", width=1.6))
        annotations.append(
            dict(
                x=projection_start_date,
                y=1.04,
                xref="x",
                yref="paper",
                text="Projection starts",
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                font=dict(size=10, color=palette["annotation_text"]),
                bgcolor=palette["annotation_bg"],
            )
        )

    if reference_lines == "min_max" and historical_reference_values:
        min_value = min(historical_reference_values)
        max_value = max(historical_reference_values)
        if math.isclose(min_value, max_value):
            shapes.append(
                dict(
                    type="line",
                    xref="paper",
                    x0=0,
                    x1=1,
                    yref="y",
                    y0=min_value,
                    y1=min_value,
                    line=dict(color="#0f766e", width=1.6, dash="dash"),
                )
            )
            annotations.append(
                dict(
                    xref="paper",
                    x=0.99,
                    yref="y",
                    y=min_value,
                    text="Historical Min / Max",
                    showarrow=False,
                    xanchor="right",
                    yanchor="bottom",
                    font=dict(size=10, color="#0f766e"),
                    bgcolor=palette["annotation_bg"],
                )
            )
        else:
            shapes.extend(
                [
                    dict(
                        type="rect",
                        xref="paper",
                        x0=0,
                        x1=1,
                        yref="y",
                        y0=min_value,
                        y1=max_value,
                        fillcolor=palette["minmax_fill"],
                        line=dict(width=0),
                        layer="below",
                    ),
                    dict(
                        type="line",
                        xref="paper",
                        x0=0,
                        x1=1,
                        yref="y",
                        y0=min_value,
                        y1=min_value,
                        line=dict(color="#0f766e", width=1.6, dash="dash"),
                    ),
                    dict(
                        type="line",
                        xref="paper",
                        x0=0,
                        x1=1,
                        yref="y",
                        y0=max_value,
                        y1=max_value,
                        line=dict(color="#b45309", width=1.6, dash="dash"),
                    ),
                ]
            )
            annotations.extend(
                [
                    dict(
                        xref="paper",
                        x=0.99,
                        yref="y",
                        y=min_value,
                        text="Historical Min",
                        showarrow=False,
                        xanchor="right",
                        yanchor="bottom",
                        font=dict(size=10, color="#0f766e"),
                        bgcolor=palette["annotation_bg"],
                    ),
                    dict(
                        xref="paper",
                        x=0.99,
                        yref="y",
                        y=max_value,
                        text="Historical Max",
                        showarrow=False,
                        xanchor="right",
                        yanchor="bottom",
                        font=dict(size=10, color="#b45309"),
                        bgcolor=palette["annotation_bg"],
                    ),
                ]
            )
    elif reference_lines == "monitoring":
        band_spec = compute_saas_monitoring_band_spec(
            monitoring_reference_records if monitoring_reference_records is not None else records,
            primary_run_for=primary_run_for,
            development_date=development_date,
        )

        if band_spec:
            green_low = band_spec["green_low"]
            green_high = band_spec["green_high"]
            lower_yellow = band_spec["amber_low_low"]
            upper_yellow = band_spec["amber_high_high"]
            axis_low, axis_high = _saas_monitoring_axis_range(visible_values, band_spec)

            shapes.extend(
                [
                    dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=axis_low, y1=lower_yellow, fillcolor="rgba(239,68,68,0.10)", line=dict(width=0), layer="below"),
                    dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=lower_yellow, y1=green_low, fillcolor="rgba(245,158,11,0.12)", line=dict(width=0), layer="below"),
                    dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_low, y1=green_high, fillcolor="rgba(34,197,94,0.12)", line=dict(width=0), layer="below"),
                    dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=green_high, y1=upper_yellow, fillcolor="rgba(245,158,11,0.12)", line=dict(width=0), layer="below"),
                    dict(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=upper_yellow, y1=axis_high, fillcolor="rgba(239,68,68,0.10)", line=dict(width=0), layer="below"),
                    dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_low, y1=green_low, line=dict(color="#f59e0b", width=1.3, dash="dash")),
                    dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=green_high, y1=green_high, line=dict(color="#f59e0b", width=1.3, dash="dash")),
                    dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=0, y1=0, line=dict(color=palette["zero_line"], width=1.3)),
                ]
            )
        else:
            axis_low = None
            axis_high = None

        if development_date is not None:
            development_marker_x = _saas_quarter_for_date(records, development_date) if is_projection_only else development_date
            if development_marker_x is not None:
                shapes.append(_vertical_marker(development_marker_x, xref="x", yref="paper", color=palette["development_marker"], dash="dot", width=1.8))

        if current_date is not None:
            current_marker_x = _saas_quarter_for_date(records, current_date) if is_projection_only else current_date
            if current_marker_x is not None:
                shapes.append(_vertical_marker(current_marker_x, xref="x", yref="paper", color=palette["scenario_date_marker"], dash="dash", width=1.8))

    if is_projection_only:
        tickvals = sorted({value for value in all_axis_values if value is not None})
        ticktext = [_format_projection_quarter_label(value) for value in tickvals]
    else:
        tickvals = _build_saas_date_ticks(all_axis_values, max_ticks=8)
        ticktext = [_format_saas_quarter_label(date_value) for date_value in tickvals]

    x_axis_title = "Quarter"
    monitoring_x_range = (
        _saas_monitoring_x_range(
            all_axis_values,
            is_projection_only=is_projection_only,
            development_date=development_marker_x if reference_lines == "monitoring" and 'development_marker_x' in locals() else development_date,
            current_date=current_marker_x if reference_lines == "monitoring" and 'current_marker_x' in locals() else current_date,
        )
        if reference_lines == "monitoring"
        else None
    )

    legend_title_text = "Scenario"
    show_bottom_legend = reference_lines != "monitoring"
    fig.update_layout(
        height=438,
        margin=dict(t=52, r=18, b=88 if reference_lines == "monitoring" else bottom_margin, l=72),
        hovermode="x unified",
        showlegend=show_bottom_legend,
        hoverdistance=2,
        hoverlabel=dict(
            bgcolor=palette["hover_bg"],
            bordercolor="rgba(255,255,255,0)",
            font=dict(size=11, color=palette["hover_font"]),
        ),
        legend=dict(
            orientation="h",
            title=dict(
                text=legend_title_text,
                font=dict(size=10.5, color=palette["legend_title"]),
            ),
            x=0,
            xanchor="left",
            y=legend_y,
            yanchor="top",
            entrywidthmode="pixels",
            entrywidth=125 if ultra_compact_legend else 110 if compact_legend else 100,
            bgcolor=palette["legend_bg"],
            bordercolor=palette["legend_border"],
            borderwidth=1,
            font=dict(size=9 if ultra_compact_legend else 10 if compact_legend else 10.5, color=palette["legend_font"]),
            itemsizing="constant",
            itemwidth=30,
            traceorder="normal",
            maxheight=0.4 if ultra_compact_legend else 0.22,
            groupclick="togglegroup",
        ),
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(
            title=dict(text=x_axis_title, font=dict(size=12, color=palette["axis_title"])),
            type="linear" if is_projection_only else "date",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont=dict(size=11, color=palette["axis_tick"]),
            gridcolor=palette["grid_color"],
            gridwidth=1,
            showline=True,
            linecolor=palette["axis_line"],
            ticks="outside",
            tickangle=0,
            automargin=True,
            showspikes=True,
            spikecolor=palette["spike_color"],
            spikedash="dot",
            spikemode="across",
            spikethickness=1,
            range=monitoring_x_range,
        ),
        yaxis=dict(
            title=dict(text=resolved_y_axis_title, font=dict(size=12, color=palette["axis_title"])),
            tickfont=dict(size=11, color=palette["axis_tick"]),
            gridcolor=palette["grid_color"],
            gridwidth=1,
            zerolinecolor=palette["zero_line"],
            showline=True,
            linecolor=palette["axis_line"],
            ticks="outside",
            automargin=True,
            range=[axis_low, axis_high] if reference_lines == "monitoring" and 'axis_low' in locals() and axis_low is not None and axis_high is not None else None,
        ),
    )
    _apply_transparent_background(fig)
    return fig
