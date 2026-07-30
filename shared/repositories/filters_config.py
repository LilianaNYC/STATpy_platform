"""Filter options for the monitoring tabs.

Each option group is sourced from whichever workbook data actually names it,
rather than a single hand-maintained list:

==================  ===================================================================
``monitoring_points``  the most recent ``MONITORING_POINT_WINDOW`` quarters per
                       reporting cycle, keyed by tab (``pd``/``lgd``/``ead``/``loss``)
                       from that tab's own ``_Performance_Metrics`` sheet -- not
                       pooled across tabs, so a tab only ever offers monitoring
                       points that exist in its own raw data. An ``all`` key
                       additionally pools every tab's sheet together for the
                       cross-portfolio Overview page. Not every historical quarter
                       is offered (that's what the trend charts are for), just the
                       recent window a "point in time" selector is meant to offer.
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
MONITORING_POINT_WINDOW = 4

# Cycles are shown most-recent-first by default; anything not in this list
# (e.g. a brand new cycle) is appended afterwards, sorted alphabetically.
_CYCLE_DISPLAY_ORDER = ["CCAR 2026", "CCAR 2025", "BAU 2025Q1"]

_MODEL_TYPE_TO_TAB = {"PD": "pd", "LGD": "lgd", "EAD": "ead"}

# Each tab's monitoring points are sourced from its own sheet only, so a tab
# never offers a quarter that doesn't actually appear in its own raw data.
# "all" pools every sheet together for the cross-portfolio Overview page.
_MONITORING_POINT_SHEETS_BY_TAB = {
    "pd": ("PD_Performance_Metrics",),
    "lgd": ("LGD_Performance_Metrics",),
    "ead": ("EAD_Performance_Metrics",),
    "loss": ("Loss_Performance_Metrics",),
    "all": _AGGREGATED_SHEET_NAMES,
}

# Not a fallback for missing/broken data -- the MEV workbook's model-
# characteristic sheet has no Loss entries at all by design (Loss has no
# per-model characteristics), so this is the tab's one permanent value.
_LOSS_MODEL_NAMES = ["All Models"]


def _read_sheet(path, sheet_name: str) -> pd.DataFrame | None:
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _quarters_by_cycle_from_sheets(sheet_names: tuple[str, ...]) -> dict[str, set[str]]:
    quarters_by_cycle: dict[str, set[str]] = {}
    for sheet_name in sheet_names:
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
    return quarters_by_cycle


def _monitoring_points_from_data() -> dict[str, dict[str, list[str]]]:
    """Monitoring point quarters per reporting cycle, keyed by tab and read
    from that tab's own sheet only (see ``_MONITORING_POINT_SHEETS_BY_TAB``)
    -- a tab never offers a monitoring point that doesn't exist in its own
    raw data. Quarter labels are ``YYYYQN`` (e.g. "2019Q1"), a fixed-width
    format that sorts correctly as plain strings.

    Per-tab (``pd``/``lgd``/``ead``/``loss``) options are capped to the most
    recent ``MONITORING_POINT_WINDOW`` quarters -- a point-in-time selector,
    not the full trend history. The ``all`` tab (Overview, which pools every
    tab's sheet together) shows every available quarter for the cycle
    uncapped, since it's the cross-portfolio view rather than a single
    model's snapshot picker.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for tab, sheet_names in _MONITORING_POINT_SHEETS_BY_TAB.items():
        quarters_by_cycle = _quarters_by_cycle_from_sheets(sheet_names)
        if not quarters_by_cycle:
            raise RuntimeError(
                f"Filter config: no 'quarter'/'reporting_cycle' data found across {', '.join(sheet_names)} "
                f"in {settings.portfolio_file} -- cannot derive monitoring points for the {tab!r} tab."
            )
        if tab == "all":
            result[tab] = {cycle: sorted(quarters) for cycle, quarters in quarters_by_cycle.items()}
        else:
            result[tab] = {
                cycle: sorted(quarters)[-MONITORING_POINT_WINDOW:]
                for cycle, quarters in quarters_by_cycle.items()
            }
    return result


def _sort_cycles(cycles: set[str]) -> list[str]:
    known = [c for c in _CYCLE_DISPLAY_ORDER if c in cycles]
    unknown = sorted(cycles - set(known))
    return known + unknown


def cycle_family(cycle: str) -> str:
    """The cycle "family" a reporting cycle belongs to -- the name's leading
    token, e.g. ``"CCAR"`` for ``"CCAR 2025"``/``"CCAR 2026"``, ``"BAU"`` for
    ``"BAU 2025Q1"``. The PD/LGD/EAD/Loss Performance tabs chain trend-chart
    history across same-family cycles (up to the selected monitoring point)
    but never across families, even when a different family's quarters would
    otherwise chronologically precede or overlap.
    """
    return cycle.split()[0] if cycle else ""


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


def monitoring_points_by_cycle(tab: str = "all") -> dict[str, list[str]]:
    """Monitoring point options per reporting cycle for one tab.

    ``tab`` is one of ``"pd"``/``"lgd"``/``"ead"``/``"loss"`` (scoped to that
    tab's own sheet) or ``"all"`` (pooled across every tab, for Overview).
    """
    per_tab = load_filter_config()["monitoring_points"]
    if tab not in per_tab:
        raise RuntimeError(f"Filter config: unknown monitoring-point tab {tab!r}; expected one of {sorted(per_tab)}.")
    return {cycle: list(quarters) for cycle, quarters in per_tab[tab].items()}


def segment_values() -> list[str]:
    return list(load_filter_config()["segments"])


def model_names(tab: str = "pd") -> list[str]:
    return list(load_filter_config()["models"].get(tab, []))
