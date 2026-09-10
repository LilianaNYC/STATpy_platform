"""Backtesting Plotly figure builders (thin wrappers).

Mirrors ``features/saas/ui/views/figures.py``: the figure *shapes* live in
``shared/ui/charts.py`` alongside the monitoring and SAAS builders (that module
owns the theme palette and the dual-panel layout), and this module only decides
which service output feeds which builder and how each metric's values are
formatted.

No calculations here -- the records arrive already computed from
``services/backtesting_service.py``.
"""

from __future__ import annotations

from .....shared.domain import constants as config
from .....shared.ui.charts import (
    build_backtesting_forecast_actual_figure,
    build_backtesting_horizon_error_figure,
    build_backtesting_vintage_curve_figure,
)

__all__ = [
    "metric_value_format",
    "build_forecast_actual_figure",
    "build_horizon_error_figure",
    "build_vintage_curve_figure",
    "build_cumulative_loss_figure",
    "build_periodic_loss_figure",
]

# How each metric's values read on an axis and in a hover label. Rates are
# percentages; EAD and NCO are currency amounts, so a percent format would be
# nonsense on them.
_VALUE_FORMATS = {
    config.BACKTESTING_METRIC_PD: (".2%", "PD"),
    config.BACKTESTING_METRIC_PD_CRR: (".2%", "PD"),
    config.BACKTESTING_METRIC_LGD: (".1%", "LGD"),
    config.BACKTESTING_METRIC_EAD: ("$,.0f", "EAD"),
    config.BACKTESTING_METRIC_NCO: ("$,.0f", "NCO"),
}


def metric_value_format(metric: str) -> tuple[str, str]:
    """``(tick format, axis label)`` for ``metric``."""
    return _VALUE_FORMATS.get(metric, (".2%", "Value"))


def build_forecast_actual_figure(view: dict, *, theme: str = "light"):
    """Forecast-versus-actual for one metric view."""
    value_format, value_label = metric_value_format(view.get("metric", ""))
    return build_backtesting_forecast_actual_figure(
        view.get("records") or [],
        value_label=value_label,
        value_format=value_format,
        theme=theme,
        empty_message=(
            "No forecast/actual pairs for the applied filters. Recent horizons "
            "have no realised outcome yet, so a narrow scope can legitimately "
            "score nothing."
        ),
    )


def build_horizon_error_figure(view: dict, *, theme: str = "light"):
    """Error-by-horizon for one metric view."""
    return build_backtesting_horizon_error_figure(
        view.get("by_horizon") or [],
        theme=theme,
        empty_message="No scored horizons for the applied filters.",
    )


def build_vintage_curve_figure(view: dict, *, theme: str = "light"):
    """Per-vintage projection paths for one metric, plotted against age."""
    value_format, value_label = metric_value_format(view.get("metric", ""))
    return build_backtesting_vintage_curve_figure(
        view.get("vintage_series") or [],
        value_label=value_label,
        value_format=value_format,
        theme=theme,
        empty_message="No vintage paths for the applied filters.",
    )


def build_cumulative_loss_figure(series, *, theme: str = "light"):
    """Cumulative net charge-off as a share of each vintage's opening exposure."""
    return build_backtesting_vintage_curve_figure(
        series or [],
        value_label="Cumulative Loss",
        value_format=".1%",
        theme=theme,
        empty_message=(
            "No cumulative loss curves for the applied filters -- this view needs "
            "both NCO and EAD rows in scope."
        ),
    )


def build_periodic_loss_figure(series, *, theme: str = "light"):
    """Loss arising in each quarter, on the same denominator as the cumulative
    view so the two charts can be read against each other."""
    return build_backtesting_vintage_curve_figure(
        series or [],
        value_label="Quarterly Loss",
        value_format=".2%",
        theme=theme,
        empty_message=(
            "No periodic loss curves for the applied filters -- this view needs "
            "both NCO and EAD rows in scope."
        ),
    )
