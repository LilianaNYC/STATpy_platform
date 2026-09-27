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
``reporting_cycles``  the distinct composite cycle values across each tab's own
                       aggregated performance-metrics table (``PD_Performance_Metrics`` /
                       ``LGD_Performance_Metrics`` / ...) -- authoritative for which
                       cycles actually have data. The workbook column is ``Run For``;
                       it arrives here as ``reporting_cycle`` because every table is
                       read through ``shared.repositories.tables``, which swaps
                       portfolio frames into the internal column shape.
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

Reads go through ``shared.repositories.tables.read_table`` rather than pandas
directly, so switching the app to its production database is a change in that
one module. Note ``_read_sheet`` here is best-effort by design: a table that
cannot be read becomes ``None`` and then an empty option list, which is why a
mistyped table name shows up as a missing filter rather than a traceback.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ...config.settings import settings
from ..domain.filter_order import alphabetical, composite_cycles_newest_first
from ..domain.constants import (
    CYCLE_KEY,
    DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
    DUMMY_MEV_TIME_SERIES_SHEET_NAME,
    MODEL_USE_CASE_COLUMN,
    REPORTING_CYCLE_COLUMN,
    REPORTING_CYCLE_KEY,
)
from .tables import read_table

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


def _read_sheet(table_name: str) -> pd.DataFrame | None:
    """One registered table, or ``None`` if it cannot be read.

    Every option group below is best-effort: a missing table degrades to an
    empty option list (or a RuntimeError raised by the caller), never a crash at
    import time. Portfolio tables arrive in the internal column shape -- see
    ``shared.repositories.tables``.
    """
    try:
        return read_table(table_name)
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _quarters_by_cycle_from_sheets(sheet_names: tuple[str, ...]) -> dict[str, set[str]]:
    quarters_by_cycle: dict[str, set[str]] = {}
    for sheet_name in sheet_names:
        df = _read_sheet(sheet_name)
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
    """Composite cycles, most recent first.

    Sorted on the **bare cycle part** ("2026", "2025Q1"), not the composite:
    comparing composites as text would put "CECL 2025Q1" above "CCAR 2026".
    Ties within one cycle fall back to the family name, so the order is total.

    This replaced a hand-maintained display list, which placed any cycle it had
    not been told about last -- "CCAR 2024" was sorting below "CECL 2025Q1"
    purely by omission.
    """
    return composite_cycles_newest_first(cycles)


def cycle_family(cycle: str) -> str:
    """The cycle "family" a reporting cycle belongs to -- the name's leading
    token, e.g. ``"CCAR"`` for ``"CCAR 2025"``/``"CCAR 2026"``, ``"CECL"`` for
    ``"CECL 2025Q1"``. The PD/LGD/EAD/Loss Performance tabs chain trend-chart
    history across same-family cycles (up to the selected monitoring point)
    but never across families, even when a different family's quarters would
    otherwise chronologically precede or overlap.
    """
    return cycle.split()[0] if cycle else ""


def _reporting_cycles_from_data() -> list[dict[str, str]]:
    cycles: set[str] = set()
    for sheet_name in _AGGREGATED_SHEET_NAMES:
        df = _read_sheet(sheet_name)
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
        df = _read_sheet(sheet_name)
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
    return alphabetical(segments)


def _model_names_from_mev_workbook() -> dict[str, list[str]]:
    df = _read_sheet(DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME)
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
            # A-Z, not the sheet's row order: where a model sits in the workbook
            # is an authoring artefact, and it surfaced as an apparently random
            # Model dropdown ("PD Model A..D, PD Corp Model, PD Model E, F").
            models[tab] = alphabetical(seen)
    missing_tabs = [tab for tab in ("pd", "lgd", "ead") if tab not in models]
    if missing_tabs:
        raise RuntimeError(
            f"Filter config: no model names found for {', '.join(missing_tabs)} in "
            f"{DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME!r} sheet of {settings.dummy_mev_data_file}."
        )
    return models


def _scenario_values_from_mev_workbook() -> list[dict[str, str]]:
    df = _read_sheet(DUMMY_MEV_TIME_SERIES_SHEET_NAME)
    if df is None or df.empty or "Scenario" not in df.columns:
        raise RuntimeError(
            f"Filter config: {DUMMY_MEV_TIME_SERIES_SHEET_NAME!r} sheet in {settings.dummy_mev_data_file} is "
            f"missing, empty, or has no 'Scenario' column."
        )
    values = alphabetical({
        text for value in df["Scenario"].dropna().unique()
        if (text := str(value).strip())
    })
    if not values:
        raise RuntimeError(
            f"Filter config: no scenario values found in {DUMMY_MEV_TIME_SERIES_SHEET_NAME!r} sheet of "
            f"{settings.dummy_mev_data_file}."
        )
    return [{"value": value, "label": value} for value in values]


def _cycle_parts_from_data() -> dict[str, dict[str, str]]:
    """``{composite: {"use_case": ..., "cycle": ...}}`` for every cycle with data.

    Read from the workbook's own ``Model Use Case`` / ``Reporting Cycle`` columns
    rather than by splitting the composite, so the sheet stays authoritative. A
    row missing either part is skipped -- it would otherwise put an unlabelled
    entry in the Model Use Case filter.
    """
    parts: dict[str, dict[str, str]] = {}
    for sheet_name in _AGGREGATED_SHEET_NAMES:
        df = _read_sheet(sheet_name)
        if df is None or df.empty:
            continue
        needed = (REPORTING_CYCLE_KEY, MODEL_USE_CASE_COLUMN, CYCLE_KEY)
        if any(column not in df.columns for column in needed):
            continue
        for composite, use_case, cycle in df[list(needed)].dropna().drop_duplicates().itertuples(index=False):
            composite, use_case, cycle = str(composite).strip(), str(use_case).strip(), str(cycle).strip()
            if composite and use_case and cycle:
                parts.setdefault(composite, {"use_case": use_case, "cycle": cycle})
    if not parts:
        raise RuntimeError(
            f"Filter config: no {MODEL_USE_CASE_COLUMN!r}/{REPORTING_CYCLE_COLUMN!r} data found across "
            f"{', '.join(_AGGREGATED_SHEET_NAMES)} in {settings.portfolio_file}."
        )
    return parts


@lru_cache(maxsize=1)
def load_filter_config() -> dict:
    """Return the monitoring filter options (see module docstring for sources)."""
    return {
        "reporting_cycles": _reporting_cycles_from_data(),
        "scenarios": _scenario_values_from_mev_workbook(),
        "monitoring_points": _monitoring_points_from_data(),
        "segments": _segment_values_from_data(),
        "models": _model_names_from_mev_workbook(),
        "cycle_parts": _cycle_parts_from_data(),
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


def model_use_case_options() -> list[dict[str, str]]:
    """Model Use Case options, A-Z.

    The **default selection is not the first entry** -- see ``default_use_case``.
    Which use case a tab lands on decides which reporting cycle's numbers it
    shows, so it tracks the most recent cycle rather than the alphabet.
    """
    parts = load_filter_config()["cycle_parts"]
    use_cases = {entry["use_case"] for entry in parts.values()}
    return [{"label": use_case, "value": use_case} for use_case in alphabetical(use_cases)]


def default_use_case(options: list[dict[str, str]] | None = None) -> str:
    """The Model Use Case a tab should open on: the owner of the most recent
    cycle.

    Kept separate from the option order on purpose. Listing the options A-Z put
    "CECL" first, and taking the default from position would have quietly moved
    every tab's landing page off the current CCAR cycle and onto CECL. Falls
    back to the first of ``options`` when the preferred use case is not among
    them -- a Model/Segment population with no CCAR data, say.
    """
    parts = load_filter_config()["cycle_parts"]
    ordered = _sort_cycles(set(parts))
    preferred = parts[ordered[0]]["use_case"] if ordered else ""
    values = [option["value"] for option in
              (options if options is not None else model_use_case_options())]
    if preferred in values:
        return preferred
    return values[0] if values else ""


def reporting_cycle_options(use_case: str | None = None) -> list[dict[str, str]]:
    """Reporting Cycle options, labelled with the bare cycle.

    The **value stays the composite** ("CCAR 2026") because that is the join key
    behind every store, figure, export and Dash element ID; only the label comes
    from the ``Reporting Cycle`` column. Pass ``use_case`` to narrow to one use
    case; omit it for every cycle that has data.
    """
    parts = load_filter_config()["cycle_parts"]
    wanted = str(use_case or "").strip()
    return [
        {"label": parts[composite]["cycle"], "value": composite}
        for composite in _sort_cycles(set(parts))
        if not wanted or parts[composite]["use_case"] == wanted
    ]


def use_case_options_for_cycles(cycles) -> list[dict[str, str]]:
    """Model Use Case options covering ``cycles`` (``None`` -> every cycle).

    Used by the PD/LGD/EAD/Loss tabs, where the cycles available depend on the
    selected Model/Segment population, so the Use Case filter must not offer a
    programme that population has no data for.
    """
    options = model_use_case_options()
    if cycles is None:
        return options
    covered = {use_case_of(cycle) for cycle in cycles}
    return [option for option in options if option["value"] in covered] or options


def cycle_options_for_cycles(cycles, use_case: str | None = None) -> list[dict[str, str]]:
    """Reporting Cycle options within ``cycles``, scoped to ``use_case``.

    Labels are the bare cycle; values stay the composite. Falls back to the full
    use-case list when the population has no recorded cycles, matching the
    pre-split behaviour of the per-tab narrowing helpers.
    """
    options = reporting_cycle_options(use_case)
    if cycles is None:
        return options
    available = set(cycles)
    return [option for option in options if option["value"] in available] or options


def use_case_of(composite: str) -> str:
    """The Model Use Case a composite cycle belongs to (``""`` if unknown)."""
    return load_filter_config()["cycle_parts"].get(str(composite or "").strip(), {}).get("use_case", "")
