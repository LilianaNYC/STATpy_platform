"""The single seam between the app and its source data.

Every table the dashboards read is registered in :data:`TABLES` and fetched
through :func:`read_table`. Today each one resolves to a sheet in one of the
bundled workbooks; in production they come from SQL Server tables instead.
Because every read funnels through here, that switch is a change to this one
module rather than to the ~17 call sites scattered across the feature loaders.

**Logical keys are the sheet names**, and for the MEV tables they are also the
production table names (``model_names``, ``mev_transformed``, ``mev_raw``,
``scenario``) -- so a caller asking for ``read_table("model_names")`` reads the
same logical thing in either mode.

Column names line up too: the production tables use the same Title Case column
names as the workbooks (``Run For``, ``Model Use Case``, ``Reporting Cycle``,
``Model Name``, ``Segment Name``, ...), so the portfolio normalization applied
here on the way out is correct for both backends.

Switching to SQL
----------------
1. Provide ``get_sql_data(database, query)`` (returns a DataFrame).
2. Uncomment :func:`_read_sql_table` below and the import it needs.
3. Point :func:`_read` at it -- or gate on an env flag.

Error behaviour is deliberately *not* softened here: :func:`read_table` raises
whatever the backend raises, because each caller already has its own
best-effort handling (some return an empty payload, some a placeholder, some
log and continue). Swallowing errors centrally would change all of them.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...config.settings import settings
from ..domain.reporting_cycle import normalize_portfolio_columns

# --- Workbooks -------------------------------------------------------------
# Which bundled workbook a table lives in. The paths themselves stay in
# config/settings.py -- these are just selectors.
PORTFOLIO = "portfolio"
MEV = "mev"
RULES = "rules"

_WORKBOOK_PATHS = {
    PORTFOLIO: lambda: settings.portfolio_file,
    MEV: lambda: settings.dummy_mev_data_file,
    RULES: lambda: settings.monitoring_thresholds_file,
}


@dataclass(frozen=True)
class Table:
    """One logical table, with both its workbook and its production coordinates.

    ``key``            logical name; also the worksheet name.
    ``workbook``       which bundled workbook holds it today.
    ``sql_database``   production database, or ``None`` where not yet decided.
    ``sql_object``     production ``[schema].[object]``, or ``None``.
    ``normalize``      apply the portfolio column swap (``Run For`` ->
                       ``reporting_cycle`` etc.) to the frame on the way out.
    """

    key: str
    workbook: str
    sql_database: str | None = None
    sql_object: str | None = None
    normalize: bool = False


# --- The registry ----------------------------------------------------------
# SQL coordinates for the MEV tables are taken from the production loader kept
# commented in features/saas/repositories/loader.py. The portfolio and rules
# tables have no confirmed mapping yet, so theirs are left None rather than
# guessed -- fill them in when the production schema is known.
_PORTFOLIO_SHEETS = (
    "PD_Performance_Metrics",
    "LGD_Performance_Metrics",
    "EAD_Performance_Metrics",
    "Loss_Performance_Metrics",
    "PD_Sensitivity_Projections",
    "LGD_Sensitivity_Projections",
    "EAD_Sensitivity_Projections",
    # Facility-level detail. Not present in the bundled workbook -- load_portfolio()
    # has always degraded to an empty frame here, and the aggregated
    # *_Performance_Metrics tables are what the pages actually read.
    "Portfolio",
)

_RULES_SHEETS = (
    "PD_Thresholds",
    "CRR_Master_Scale",
    "RAG_Assignment_PD",
    "LGD_Thresholds",
    "EAD_Thresholds",
    "Loss_Thresholds",
    "Scenario_Test_Thresholds",
    "fallback_amber_rules",
    "monitoring_actions",
)

TABLES: dict[str, Table] = {
    # MEV / model configuration -- STAT_Config in production.
    "model_names": Table("model_names", MEV, "STAT_Config", "[dbo].[model_names]"),
    "mev_transformed": Table("mev_transformed", MEV, "STAT_Config", "[dbo].[mev_transformed]"),
    "mev_raw": Table("mev_raw", MEV, "STAT_Config", "[dbo].[mev_raw]"),
    # In production the scenario time series lives per active cycle, in
    # STAT_Inputs_<Run For>_BHC.[input].[scenario]; the workbook keeps all
    # cycles in one sheet. See _read_sql_table for that fan-out.
    "scenario": Table("scenario", MEV, None, "[input].[scenario]"),
    # Aggregated performance metrics + projections.
    **{name: Table(name, PORTFOLIO, normalize=True) for name in _PORTFOLIO_SHEETS},
    # Thresholds and rules. Likely to stay file-based config even in
    # production, hence no SQL coordinates.
    **{name: Table(name, RULES) for name in _RULES_SHEETS},
}


def table(key: str) -> Table:
    """The registered :class:`Table` for ``key``."""
    try:
        return TABLES[key]
    except KeyError:
        raise KeyError(
            f"Unregistered table {key!r}. Add it to TABLES in "
            f"{__name__} so it has both workbook and production coordinates."
        ) from None


def _read_excel_table(spec: Table, usecols: list[str] | None) -> pd.DataFrame:
    """Read one sheet, opening the workbook per call.

    Deliberately not caching the ``pd.ExcelFile`` handle: measured at ~8ms saved
    across a whole load, while a cached handle outlives a test's monkeypatch of
    ``pd.ExcelFile`` and would then be served to real code.
    """
    path = _WORKBOOK_PATHS[spec.workbook]()
    return pd.read_excel(path, sheet_name=spec.key, usecols=usecols)


# def _read_sql_table(spec: Table, usecols: list[str] | None) -> pd.DataFrame:
#     """Production twin of :func:`_read_excel_table`.
#
#     Mirrors the commented SQL loader in features/saas/repositories/loader.py:
#     configuration tables come from ``STAT_Config``, while the scenario time
#     series is per active cycle and must be stitched together -- active cycles
#     being those with ``run_details.Status == "Y"``.
#     """
#     if spec.sql_object is None:
#         raise KeyError(f"{spec.key!r} has no production mapping yet.")
#
#     # Per-cycle fan-out: one database per active Run For.
#     if spec.key == "scenario":
#         run_details = get_sql_data("STAT_Config", "SELECT * FROM [dbo].[run_details]")
#         active = [
#             str(value).strip()
#             for value in run_details[run_details["Status"] == "Y"]["Run For"].tolist()
#             if str(value).strip()
#         ]
#         frames: list[pd.DataFrame] = []
#         for run_for in active:
#             database = f"STAT_Inputs_{run_for.replace(' ', '_')}_BHC"
#             try:
#                 frames.append(get_sql_data(database, f"SELECT * FROM {spec.sql_object}"))
#             except Exception as exc:  # noqa: BLE001 - one cycle's DB being down shouldn't blank the rest
#                 log.warning("Failed to load %s from %s: %s", spec.sql_object, database, exc)
#         if not frames:
#             return pd.DataFrame()
#         df = pd.concat(frames, ignore_index=True)
#     else:
#         df = get_sql_data(spec.sql_database, f"SELECT * FROM {spec.sql_object}")
#
#     return df[usecols] if usecols else df


def _read(spec: Table, usecols: list[str] | None) -> pd.DataFrame:
    """The active backend. Swap for ``_read_sql_table`` to go to production."""
    return _read_excel_table(spec, usecols)


def read_table(key: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """Read one registered table.

    Raises whatever the backend raises (missing file, missing sheet, ...) so
    each caller keeps its own best-effort handling. Portfolio tables come back
    in the internal column shape -- see
    :func:`shared.domain.reporting_cycle.normalize_portfolio_columns`.
    """
    spec = table(key)
    df = _read(spec, usecols)
    return normalize_portfolio_columns(df) if spec.normalize else df


__all__ = ["PORTFOLIO", "MEV", "RULES", "TABLES", "Table", "read_table", "table"]
