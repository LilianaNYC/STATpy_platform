"""MEV (Macroeconomic Variable) Range helpers for the PD Performance dashboard.

Ports the MEV catalog / threshold / RAG helpers from
``pages/monitoring_pd_models_page.py`` (``getPdMevSelectedModels``,
``getPdMevAvailableNamesForModels``, ``getPdMevVisiblePeriods``,
``calculatePdMevThresholds``, ``calculatePdMevRag``,
``calculatePdMevWorstRagAfterQuarter``, ``getPdMevModelDevelopmentDates``,
``getPdMevChartId``, ``getPdMevChartColor``, ``formatPdMevValue``,
``slugifyPdToken``).
"""

from __future__ import annotations

import re
from typing import Any

from . import constants as config
from .rank_ordering import compare_pd_quarter_labels, _pd_quarter_sort_key
from .calculations import PdFilterContext, _finite, _to_number

_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SLUG_TRIM_RE = re.compile(r"^-+|-+$")


def slugify_pd_token(value: str | None) -> str:
    """Port of ``slugifyPdToken``."""
    slug = _SLUG_NON_ALNUM_RE.sub("-", str(value or "").lower())
    return _SLUG_TRIM_RE.sub("", slug)


def format_pd_mev_value(value: Any) -> str:
    """Port of ``formatPdMevValue``."""
    number = _to_number(value)
    if number is None or not _finite(number):
        return "—"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Catalog filtering
# ---------------------------------------------------------------------------


def get_pd_mev_selected_models(mev_catalog: dict[str, Any], ctx: PdFilterContext) -> list[str]:
    """Port of ``getPdMevSelectedModels``."""
    available_models = list(mev_catalog.keys())
    if ctx.models:
        model_names = [name for name in available_models if name in ctx.models]
    else:
        model_names = list(available_models)

    if ctx.segment != "all":
        model_names = [
            name for name in model_names
            if ctx.segment in (mev_catalog.get(name, {}).get("segments") or [])
        ]
    return model_names


def get_pd_mev_available_names_for_models(mev_catalog: dict[str, Any], model_names: list[str]) -> list[str]:
    """Port of ``getPdMevAvailableNamesForModels``."""
    names: set[str] = set()
    for model_name in model_names:
        names.update((mev_catalog.get(model_name, {}).get("mevs") or {}).keys())
    return sorted(names)


def get_pd_mev_visible_periods(mev_catalog: dict[str, Any], model_names: list[str], mev_names: list[str]) -> list[str]:
    """Port of ``getPdMevVisiblePeriods``."""
    periods: set[str] = set()
    for model_name in model_names:
        mevs = mev_catalog.get(model_name, {}).get("mevs") or {}
        for mev_name, mev_data in mevs.items():
            if mev_name not in mev_names:
                continue
            periods.update((mev_data or {}).get("time_series", {}).keys())
    return sorted(periods, key=_pd_quarter_sort_key)


def get_pd_mev_model_development_dates(model_data: dict[str, Any]) -> list[str]:
    """Port of ``getPdMevModelDevelopmentDates``."""
    dates = {
        mev.get("dev_range", {}).get("development_date")
        for mev in (model_data.get("mevs") or {}).values()
        if mev.get("dev_range", {}).get("development_date")
    }
    return sorted(dates)


# ---------------------------------------------------------------------------
# Thresholds / RAG
# ---------------------------------------------------------------------------


def calculate_pd_mev_thresholds(dev_range: dict[str, Any] | None) -> dict[str, Any] | None:
    """Port of ``calculatePdMevThresholds``."""
    dev_range = dev_range or {}
    green_min = _to_number(dev_range.get("min"))
    green_max = _to_number(dev_range.get("max"))
    mean = _to_number(dev_range.get("mean"))
    two_std_lower = _to_number(dev_range.get("2std_lower"))
    two_std_upper = _to_number(dev_range.get("2std_upper"))
    if green_min is None or green_max is None or mean is None:
        return None

    lower_std = max((mean - two_std_lower) / 2, 0) if two_std_lower is not None else 0
    upper_std = max((two_std_upper - mean) / 2, 0) if two_std_upper is not None else 0
    return {
        "green_min": green_min,
        "green_max": green_max,
        "amber_lower": min(green_min, green_min - 2 * lower_std),
        "amber_upper": max(green_max, green_max + 2 * upper_std),
        "development_date": dev_range.get("development_date") or "",
    }


def calculate_pd_mev_rag(value: Any, thresholds: dict[str, Any] | None) -> str:
    """Port of ``calculatePdMevRag``."""
    number = _to_number(value)
    if number is None or not _finite(number) or not thresholds:
        return "N/A"
    if number < thresholds["amber_lower"] or number > thresholds["amber_upper"]:
        return "Red"
    if number < thresholds["green_min"] or number > thresholds["green_max"]:
        return "Amber"
    return "Green"


def calculate_pd_mev_worst_rag_after_quarter(mev_data: dict[str, Any], start_quarter: str) -> str:
    """Port of ``calculatePdMevWorstRagAfterQuarter``."""
    thresholds = calculate_pd_mev_thresholds(mev_data.get("dev_range") or {})
    if not thresholds:
        return "N/A"

    post_scenario_values = []
    for quarter, raw_value in (mev_data.get("time_series") or {}).items():
        if start_quarter and compare_pd_quarter_labels(quarter, start_quarter) < 0:
            continue
        value = _to_number(raw_value)
        if value is not None and _finite(value):
            post_scenario_values.append(value)

    if not post_scenario_values:
        return "N/A"

    worst_rag = "Green"
    for value in post_scenario_values:
        rag = calculate_pd_mev_rag(value, thresholds)
        if rag == "Red":
            return "Red"
        if rag == "Amber":
            worst_rag = "Amber"
    return worst_rag


# ---------------------------------------------------------------------------
# Chart identity
# ---------------------------------------------------------------------------


def get_pd_mev_chart_id(model_name: str, mev_name: str) -> str:
    """Port of ``getPdMevChartId``."""
    return f"pd-mev-chart-{slugify_pd_token(model_name)}-{slugify_pd_token(mev_name)}"


def get_pd_mev_chart_color(index: int) -> str:
    """Port of ``getPdMevChartColor``."""
    palette = config.PD_MEV_PALETTE
    return palette[index % len(palette)]
