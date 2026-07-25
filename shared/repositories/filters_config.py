"""Filter options for the monitoring tabs.

Each option group is sourced from whichever workbook data actually names it,
rather than a single hand-maintained list:

==================  ===================================================================
``monitoring_points``  the most recent ``_MONITORING_POINT_WINDOW`` quarters per
                       reporting cycle, from the same ``quarter`` column ``segments``
                       reads -- not every historical quarter (that's what the
                       trend charts are for), just the recent window a "point in
                       time" selector is meant to offer.
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

_AGGREGATED_SHEET_NAMES = (
    "PD_Performance_Metrics",
    "LGD_Performance_Metrics",
    "EAD_Performance_Metrics",
    "Loss_Performance_Metrics",
)

# How many of a cycle's most recent quarters count as "monitoring points" --
# a point-in-time selector, not the full trend history. Matches the size of
# the curated list the portfolio workbook's now-unused "Filters" sheet used
# to hand-maintain (e.g. CCAR 2026 had exactly 4: 2025Q4-2026Q3).
_MONITORING_POINT_WINDOW = 4

# Cycles are shown most-recent-first by default; anything not in this list
# (e.g. a brand new cycle) is appended afterwards, sorted alphabetically.
_CYCLE_DISPLAY_ORDER = ["CCAR 2026", "CCAR 2025", "BAU 2025Q1"]

_MODEL_TYPE_TO_TAB = {"PD": "pd", "LGD": "lgd", "EAD": "ead"}

# Not a fallback for missing/broken data -- the MEV workbook's model-
# characteristic sheet has no Loss entries at all by design (Loss has no
# per-model characteristics), so this is the tab's one permanent value.
_LOSS_MODEL_NAMES = ["All Models"]


def _read_sheet(path, sheet_name: str) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _monitoring_points_from_data() -> dict[str, list[str]]:
    """The most recent ``_MONITORING_POINT_WINDOW`` quarters per reporting
    cycle, from the same ``quarter``/``reporting_cycle`` columns
    ``_reporting_cycles_from_data``/``_segment_values_from_data`` already
    read. Quarter labels are ``YYYYQN`` (e.g. "2019Q1"), a fixed-width format
    that sorts correctly as plain strings.
    """
    quarters_by_cycle: dict[str, set[str]] = {}
    for sheet_name in _AGGREGATED_SHEET_NAMES:
        df = _read_sheet(settings.portfolio_file, sheet_name)
        if df is None or "reporting_cycle" not in df.columns or "quarter" not in df.columns:
            continue
        for cycle_value, group in df.groupby("reporting_cycle"):
            cycle = str(cycle_value).strip()
            if not cycle:
                continue
            quarters_by_cycle.setdefault(cycle, set()).update(
                text for value in group["quarter"].dropna().unique() if (text := str(value).strip())
            )

    if not quarters_by_cycle:
        raise RuntimeError(
            f"Filter config: no 'quarter'/'reporting_cycle' data found across {', '.join(_AGGREGATED_SHEET_NAMES)} "
            f"in {settings.portfolio_file} -- cannot derive monitoring points."
        )
    return {
        cycle: sorted(quarters)[-_MONITORING_POINT_WINDOW:]
        for cycle, quarters in quarters_by_cycle.items()
    }


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
        raise RuntimeError(
            f"Filter config: no reporting cycles found across {', '.join(_AGGREGATED_SHEET_NAMES)} in "
            f"{settings.portfolio_file}."
        )
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
    if not segments:
        raise RuntimeError(
            f"Filter config: no real segment values found across {', '.join(_AGGREGATED_SHEET_NAMES)} in "
            f"{settings.portfolio_file}."
        )
    return sorted(segments)


def _model_names_from_mev_workbook() -> dict[str, list[str]]:
    df = _read_sheet(settings.dummy_mev_data_file, DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME)
    if df is None or df.empty or "Model Type" not in df.columns or "Model Descriptive Name" not in df.columns:
        raise RuntimeError(
            f"Filter config: {DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME!r} sheet in "
            f"{settings.dummy_mev_data_file} is missing, empty, or has no 'Model Type' / "
            f"'Model Descriptive Name' columns -- cannot derive model names."
        )

    models: dict[str, list[str]] = {"loss": list(_LOSS_MODEL_NAMES)}
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
    missing_tabs = [tab for tab in ("pd", "lgd", "ead") if tab not in models]
    if missing_tabs:
        raise RuntimeError(
            f"Filter config: no model names found for {', '.join(missing_tabs)} in "
            f"{DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME!r} sheet of {settings.dummy_mev_data_file}."
        )
    return models


def _scenario_values_from_mev_workbook() -> list[dict[str, str]]:
    df = _read_sheet(settings.dummy_mev_data_file, DUMMY_MEV_TIME_SERIES_SHEET_NAME)
    if df is None or df.empty or "Scenario" not in df.columns:
        raise RuntimeError(
            f"Filter config: {DUMMY_MEV_TIME_SERIES_SHEET_NAME!r} sheet in {settings.dummy_mev_data_file} is "
            f"missing, empty, or has no 'Scenario' column."
        )
    values = sorted({
        text for value in df["Scenario"].dropna().unique()
        if (text := str(value).strip())
    })
    if not values:
        raise RuntimeError(
            f"Filter config: no scenario values found in {DUMMY_MEV_TIME_SERIES_SHEET_NAME!r} sheet of "
            f"{settings.dummy_mev_data_file}."
        )
    return [{"value": value, "label": value} for value in values]


@lru_cache(maxsize=1)
def load_filter_config() -> dict:
    """Return the monitoring filter options (see module docstring for sources)."""
    return {
        "reporting_cycles": _reporting_cycles_from_data(),
        "scenarios": _scenario_values_from_mev_workbook(),
        "monitoring_points": _monitoring_points_from_data(),
        "segments": _segment_values_from_data(),
        "models": _model_names_from_mev_workbook(),
    }


def monitoring_points_by_cycle() -> dict[str, list[str]]:
    return {k: list(v) for k, v in load_filter_config()["monitoring_points"].items()}


def segment_values() -> list[str]:
    return list(load_filter_config()["segments"])


def model_names(tab: str = "pd") -> list[str]:
    return list(load_filter_config()["models"].get(tab, []))
