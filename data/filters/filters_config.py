"""Filter options for the monitoring tabs, sourced from the ``Filters`` tab.

The ``Filters`` sheet in the portfolio workbook is a single, easy-to-edit long
table that drives every dropdown in the monitoring tabs. Each row is one option:

==================  ===================================================
``filter_type``     ``reporting_cycle`` | ``scenario`` | ``monitoring_point``
                    | ``segment`` | ``model``
``value``           the value stored / matched in the app
``parent``          scopes the option: the reporting cycle for a
                    ``monitoring_point``, or the tab (``pd``/``lgd``/``ead``/
                    ``loss``) for a ``model``; blank otherwise
``label``           the text shown in the dropdown (defaults to ``value``)
``order``           sort order within the group (lower first)
==================  ===================================================

To add or remove a filter element, add or delete a row in that sheet — no code
changes are required.

This module lives in its own top-level ``data/filters/`` package rather than
``features/monitoring/repositories/`` (where the rest of monitoring's
feature-private data loading lives) because it's read by the shared
``components.filters`` module, which both the monitoring and SAAS dashboards
depend on. Moving it into a feature-private package would make a shared
component reach into another feature's internals.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ..analytics import constants as config

FILTERS_SHEET_NAME = "Filters"

# Fallback used if the workbook has no ``Filters`` sheet, so the app still runs.
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
        "pd": ["PD Model A", "PD Model B"],
        "lgd": ["LGD Model A"],
        "ead": ["EAD Model A"],
        "loss": ["Loss Model"],
    },
}


@lru_cache(maxsize=1)
def load_filter_config() -> dict:
    """Return the monitoring filter options, read from the ``Filters`` sheet."""
    try:
        df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=FILTERS_SHEET_NAME)
    except (FileNotFoundError, ValueError, KeyError):
        return dict(_DEFAULTS)

    if df.empty or "filter_type" not in df.columns:
        return dict(_DEFAULTS)

    df = df.copy()
    df["order"] = pd.to_numeric(df.get("order"), errors="coerce").fillna(0)
    if "label" not in df.columns:
        df["label"] = df["value"]
    df["label"] = df["label"].fillna(df["value"])
    if "parent" not in df.columns:
        df["parent"] = ""
    df["parent"] = df["parent"].fillna("").astype(str).str.strip()

    def _rows(filter_type: str) -> pd.DataFrame:
        sub = df[df["filter_type"].astype(str).str.strip() == filter_type]
        return sub.sort_values("order")

    reporting_cycles = [
        {"value": str(r["value"]).strip(), "label": str(r["label"]).strip()}
        for _, r in _rows("reporting_cycle").iterrows()
    ]
    scenarios = [
        {"value": str(r["value"]).strip(), "label": str(r["label"]).strip()}
        for _, r in _rows("scenario").iterrows()
    ]
    segments = [str(r["value"]).strip() for _, r in _rows("segment").iterrows()]

    monitoring_points: dict[str, list[str]] = {}
    for _, r in _rows("monitoring_point").iterrows():
        monitoring_points.setdefault(r["parent"], []).append(str(r["value"]).strip())

    models: dict[str, list[str]] = {}
    for _, r in _rows("model").iterrows():
        models.setdefault(r["parent"] or "pd", []).append(str(r["value"]).strip())

    return {
        "reporting_cycles": reporting_cycles or _DEFAULTS["reporting_cycles"],
        "scenarios": scenarios or _DEFAULTS["scenarios"],
        "monitoring_points": monitoring_points or _DEFAULTS["monitoring_points"],
        "segments": segments or _DEFAULTS["segments"],
        "models": models or _DEFAULTS["models"],
    }


def reporting_cycle_options() -> list[dict]:
    return [dict(c) for c in load_filter_config()["reporting_cycles"]]


def scenario_options() -> list[dict]:
    return [dict(s) for s in load_filter_config()["scenarios"]]


def monitoring_points_by_cycle() -> dict[str, list[str]]:
    return {k: list(v) for k, v in load_filter_config()["monitoring_points"].items()}


def segment_values() -> list[str]:
    return list(load_filter_config()["segments"])


def model_names(tab: str = "pd") -> list[str]:
    return list(load_filter_config()["models"].get(tab, []))
