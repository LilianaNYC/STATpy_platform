"""Filter options for the monitoring tabs.

Each option group is sourced from whichever workbook data actually names it,
rather than a single hand-maintained list:

==================  ===================================================================
``monitoring_points``  the portfolio workbook's ``Filters`` sheet (``monitoring_point``
                       rows) -- the only place that records which quarters belong to
                       which reporting cycle.
``reporting_cycles``  the distinct ``reporting_cycle`` values across each tab's own
                       aggregated performance-metrics sheet in the portfolio workbook
                       (``PD_Performance_Metrics`` / ``LGD_Performance_Metrics`` / ...) --
                       authoritative for which cycles actually have data.
``segments``           the distinct ``segment`` values (excluding the "All" aggregate)
                       across those same sheets.
``models``             ``dummy_mev_data.xlsx``'s ``model_names`` sheet, grouped by
                       Model Type -> Model Descriptive Name. Loss has no entry there
                       and keeps a fixed "All Models" placeholder.
``scenarios``          the distinct ``Scenario`` values in ``dummy_mev_data.xlsx``'s
                       own scenario sheet (see also the per-cycle narrowing done in
                       the monitoring callbacks via ``mev_scenarios_by_cycle``).
==================  ===================================================================

This module lives in its own top-level ``shared/repositories/`` package rather than
``features/monitoring/repositories/`` (where the rest of monitoring's
feature-private data loading lives) because it's read by the shared
``shared.ui.controls`` module, which both the monitoring and SAAS dashboards
depend on. Moving it into a feature-private package would make a shared
component reach into another feature's internals.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ...config.settings import settings
from ..domain.constants import (
    DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
    DUMMY_MEV_TIME_SERIES_SHEET_NAME,
)

FILTERS_SHEET_NAME = "Filters"

_AGGREGATED_SHEET_NAMES = (
    "PD_Performance_Metrics",
    "LGD_Performance_Metrics",
    "EAD_Performance_Metrics",
    "Loss_Performance_Metrics",
)

# Cycles are shown most-recent-first by default; anything not in this list
# (e.g. a brand new cycle) is appended afterwards, sorted alphabetically.
_CYCLE_DISPLAY_ORDER = ["CCAR 2026", "CCAR 2025", "BAU 2025Q1"]

_MODEL_TYPE_TO_TAB = {"PD": "pd", "LGD": "lgd", "EAD": "ead"}

# Fallback used if a workbook/sheet is missing, so the app still runs.
_DEFAULTS: dict = {
    "reporting_cycles": [
        {"value": "CCAR 2026", "label": "CCAR 2026"},
        {"value": "CCAR 2025", "label": "CCAR 2025"},
        {"value": "BAU 2025Q1", "label": "BAU 2025Q1"},
    ],
    "scenarios": [
        {"value": "intsevere", "label": "intsevere"},
        {"value": "baseline", "label": "baseline"},
        {"value": "other", "label": "other"},
    ],
    "monitoring_points": {
        "CCAR 2026": ["2025Q4", "2026Q1", "2026Q2", "2026Q3"],
        "CCAR 2025": ["2024Q4", "2025Q1", "2025Q2", "2025Q3"],
        "BAU 2025Q1": ["2025Q1"],
    },
    "segments": ["Cyclical", "Defensive", "O&M", "LoL", "IVB"],
    "models": {
        "pd": ["PD Model A", "PD Model B", "PD Model C", "PD Model D"],
        "lgd": ["LGD Model A", "LGD Model B"],
        "ead": ["EAD Model A", "EAD Model B"],
        "loss": ["All Models"],
    },
}


def _read_sheet(path, sheet_name: str) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _monitoring_points_from_filters_sheet() -> dict[str, list[str]]:
    df = _read_sheet(settings.portfolio_file, FILTERS_SHEET_NAME)
    if df is None or df.empty or "filter_type" not in df.columns:
        return dict(_DEFAULTS["monitoring_points"])

    df = df.copy()
    df["order"] = pd.to_numeric(df.get("order"), errors="coerce").fillna(0)
    if "parent" not in df.columns:
        df["parent"] = ""
    df["parent"] = df["parent"].fillna("").astype(str).str.strip()

    rows = df[df["filter_type"].astype(str).str.strip() == "monitoring_point"].sort_values("order")
    monitoring_points: dict[str, list[str]] = {}
    for _, r in rows.iterrows():
        monitoring_points.setdefault(r["parent"], []).append(str(r["value"]).strip())
    return monitoring_points or dict(_DEFAULTS["monitoring_points"])


def _sort_cycles(cycles: set[str]) -> list[str]:
    known = [c for c in _CYCLE_DISPLAY_ORDER if c in cycles]
    unknown = sorted(cycles - set(known))
    return known + unknown


def _reporting_cycles_from_data() -> list[dict[str, str]]:
    cycles: set[str] = set()
    for sheet_name in _AGGREGATED_SHEET_NAMES:
        df = _read_sheet(settings.portfolio_file, sheet_name)
        if df is not None and "reporting_cycle" in df.columns:
            cycles.update(
                text for value in df["reporting_cycle"].dropna().unique()
                if (text := str(value).strip())
            )
    if not cycles:
        return list(_DEFAULTS["reporting_cycles"])
    return [{"value": cycle, "label": cycle} for cycle in _sort_cycles(cycles)]


def _segment_values_from_data() -> list[str]:
    segments: set[str] = set()
    for sheet_name in _AGGREGATED_SHEET_NAMES:
        df = _read_sheet(settings.portfolio_file, sheet_name)
        if df is not None and "segment" in df.columns:
            segments.update(
                text for value in df["segment"].dropna().unique()
                if (text := str(value).strip()) and text.lower() != "all"
            )
    return sorted(segments) or list(_DEFAULTS["segments"])


def _model_names_from_mev_workbook() -> dict[str, list[str]]:
    df = _read_sheet(settings.dummy_mev_data_file, DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME)
    models: dict[str, list[str]] = {"loss": list(_DEFAULTS["models"]["loss"])}
    if df is None or df.empty or "Model Type" not in df.columns or "Model Descriptive Name" not in df.columns:
        for tab in ("pd", "lgd", "ead"):
            models[tab] = list(_DEFAULTS["models"][tab])
        return models

    for model_type, group in df.groupby("Model Type"):
        tab = _MODEL_TYPE_TO_TAB.get(str(model_type).strip().upper())
        if not tab:
            continue
        seen: list[str] = []
        for name in group["Model Descriptive Name"]:
            name = str(name).strip()
            if name and name not in seen:
                seen.append(name)
        if seen:
            models[tab] = seen
    for tab in ("pd", "lgd", "ead"):
        models.setdefault(tab, list(_DEFAULTS["models"][tab]))
    return models


def _scenario_values_from_mev_workbook() -> list[dict[str, str]]:
    df = _read_sheet(settings.dummy_mev_data_file, DUMMY_MEV_TIME_SERIES_SHEET_NAME)
    if df is None or df.empty or "Scenario" not in df.columns:
        return list(_DEFAULTS["scenarios"])
    values = sorted({
        text for value in df["Scenario"].dropna().unique()
        if (text := str(value).strip())
    })
    if not values:
        return list(_DEFAULTS["scenarios"])
    return [{"value": value, "label": value} for value in values]


@lru_cache(maxsize=1)
def load_filter_config() -> dict:
    """Return the monitoring filter options (see module docstring for sources)."""
    return {
        "reporting_cycles": _reporting_cycles_from_data(),
        "scenarios": _scenario_values_from_mev_workbook(),
        "monitoring_points": _monitoring_points_from_filters_sheet(),
        "segments": _segment_values_from_data(),
        "models": _model_names_from_mev_workbook(),
    }


def monitoring_points_by_cycle() -> dict[str, list[str]]:
    return {k: list(v) for k, v in load_filter_config()["monitoring_points"].items()}


def segment_values() -> list[str]:
    return list(load_filter_config()["segments"])


def model_names(tab: str = "pd") -> list[str]:
    return list(load_filter_config()["models"].get(tab, []))
