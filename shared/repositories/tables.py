"""The single seam between the app and its source data.

Every table the dashboards read is registered in :data:`TABLES` and fetched
through :func:`read_table`. Today each one resolves to a sheet in one of the
bundled workbooks; in production they come from SQL Server tables instead.
Because every read funnels through here, that switch is a change to this one
module rather than to the ~17 call sites scattered across the feature loaders.

**Logical keys are the sheet names**, and for the MEV tables they are also the
production table names (``model_names``, ``mev_transformed``, ``mev_raw``,
``scenario``) -- so a caller asking for ``read_table("model_names")`` reads the
same logical thing in either mode. The portfolio tables are the exception: their
production objects are lowercase snake_case (``PD_Performance_Metrics`` ->
``[output].[pd_performance_metrics]``), so the real spelling lives in
``sql_object`` and must not be re-derived from the key.

Two production shapes
---------------------
* **Flat** -- one row set in ``STAT_Config`` (the MEV/model configuration).
* **Per reporting cycle** -- one database per active ``Run For``: the scenario
  time series in ``STAT_Inputs_<Run For>_BHC.[input].[scenario]`` and every
  portfolio table in ``STAT_Outputs_<Run For>_BHC.[output].<table>``. The
  bundled workbooks keep every cycle in one sheet, so these are fanned out and
  concatenated on read (:attr:`Table.is_per_cycle`). Callers above this line get
  the same all-cycles frame either way and never learn which backend is live.

Column names line up too: the production tables use the same Title Case column
names as the workbooks (``Run For``, ``Model Use Case``, ``Reporting Cycle``,
``Model Name``, ``Segment Name``, ...), so the portfolio normalization applied
here on the way out is correct for both backends.

Switching to SQL
----------------
1. Provide ``get_sql_data(database, query)`` (returns a DataFrame).
2. Uncomment :func:`_read_sql_table` below. It needs three names this module
   does not import while it stays commented: ``get_sql_data``, a ``log``
   logger, and ``RUN_FOR_COLUMN`` from ``..domain.constants``.
3. Point :func:`_read` at it -- or gate on an env flag.

The commented body is kept *inert on purpose*: it cannot run, so it cannot
fail, and the coordinates above stay plain data until someone deliberately
turns the backend on.

Error behaviour is deliberately *not* softened here: :func:`read_table` raises
whatever the backend raises, because each caller already has its own
best-effort handling (some return an empty payload, some a placeholder, some
log and continue). Swallowing errors centrally would change all of them.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ...config.settings import settings
from ..domain.constants import DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME, MODEL_KEY
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
                       May be a **template** containing ``{run_for}`` -- see
                       :attr:`is_per_cycle`.
    ``sql_object``     production ``[schema].[object]``, or ``None``.
    ``normalize``      apply the portfolio column swap (``Run For`` ->
                       ``reporting_cycle`` etc.) to the frame on the way out.
    """

    key: str
    workbook: str
    sql_database: str | None = None
    sql_object: str | None = None
    normalize: bool = False

    @property
    def is_per_cycle(self) -> bool:
        """Does this table live in one database *per reporting cycle*?

        Production splits the per-cycle data across one database per active
        ``Run For`` (``STAT_Inputs_CCAR_2026_BHC``,
        ``STAT_Outputs_CCAR_2026_BHC``, ...), while the bundled workbooks keep
        every cycle in one sheet. A table whose ``sql_database`` carries the
        ``{run_for}`` placeholder is read by fanning out across the active
        cycles and concatenating, which reproduces the sheet's shape -- so
        nothing above this seam has to know which backend it came from.
        """
        return bool(self.sql_database) and "{run_for}" in self.sql_database

    def database_for(self, run_for: str) -> str:
        """The database holding this table for one reporting cycle.

        ``CCAR 2026`` -> ``STAT_Outputs_CCAR_2026_BHC``. Spaces become
        underscores, matching the convention the SAAS loader already uses.
        """
        if not self.sql_database:
            raise KeyError(f"{self.key!r} has no production database mapping yet.")
        return self.sql_database.format(run_for=run_for.replace(" ", "_"))


# --- The registry ----------------------------------------------------------
# SQL coordinates for the MEV tables are taken from the production loader kept
# commented in features/saas/repositories/loader.py. The portfolio tables are
# monitoring *outputs*, one database per active reporting cycle --
# ``STAT_Outputs_<Run For>_BHC.[output].<table>`` -- mirroring the
# ``STAT_Inputs_<Run For>_BHC.[input].[scenario]`` fan-out the scenario table
# already uses. The rules tables are likely to stay file-based config, so
# theirs stay None rather than being guessed.
#
# Production object names are lowercase snake_case, so unlike the MEV tables
# the logical key is *not* the production table name -- ``sql_object`` carries
# the real spelling and nothing should re-derive it from the key.
_PORTFOLIO_DATABASE = "STAT_Outputs_{run_for}_BHC"

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
    # cycles in one sheet. The {run_for} placeholder is what marks it per-cycle
    # -- see Table.is_per_cycle and the fan-out in _read_sql_table.
    "scenario": Table("scenario", MEV, "STAT_Inputs_{run_for}_BHC", "[input].[scenario]"),
    # Aggregated performance metrics + projections. Per reporting cycle in
    # production; one sheet holding every cycle in the workbook.
    **{
        name: Table(
            name,
            PORTFOLIO,
            _PORTFOLIO_DATABASE,
            f"[output].[{name.lower()}]",
            normalize=True,
        )
        for name in _PORTFOLIO_SHEETS
    },
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
#     Two shapes, told apart by :attr:`Table.is_per_cycle`:
#
#     * **Flat** -- the configuration tables, one row set in ``STAT_Config``.
#     * **Per cycle** -- the scenario time series
#       (``STAT_Inputs_<Run For>_BHC.[input].[scenario]``) and every portfolio
#       table (``STAT_Outputs_<Run For>_BHC.[output].<table>``). Production
#       splits these across one database per active reporting cycle, while the
#       workbook keeps every cycle in one sheet, so they are stitched back
#       together here. Active cycles are those with ``run_details.Status ==
#       "Y"``.
#
#     Keeping the stitch *here* is the point of the seam: callers above get the
#     same all-cycles frame either way, so none of them learns which backend is
#     live. One cycle's database being unreachable degrades to a warning and the
#     remaining cycles, rather than blanking the whole dashboard.
#     """
#     if spec.sql_object is None:
#         raise KeyError(f"{spec.key!r} has no production mapping yet.")
#
#     if not spec.is_per_cycle:
#         df = get_sql_data(spec.sql_database, f"SELECT * FROM {spec.sql_object}")
#         return df[usecols] if usecols else df
#
#     run_details = get_sql_data("STAT_Config", "SELECT * FROM [dbo].[run_details]")
#     active = [
#         str(value).strip()
#         for value in run_details[run_details["Status"] == "Y"]["Run For"].tolist()
#         if str(value).strip()
#     ]
#
#     frames: list[pd.DataFrame] = []
#     for run_for in active:
#         database = spec.database_for(run_for)
#         try:
#             cycle_df = get_sql_data(database, f"SELECT * FROM {spec.sql_object}")
#         except Exception as exc:  # noqa: BLE001 - one cycle's DB being down shouldn't blank the rest
#             log.warning("Failed to load %s from %s: %s", spec.sql_object, database, exc)
#             continue
#         # The cycle is implied by *which database* the rows came from, so a
#         # per-cycle table need not carry "Run For" as a column -- but every
#         # portfolio frame above this seam is keyed on it (normalize_portfolio_
#         # columns turns it into ``reporting_cycle``, the join key behind every
#         # store, figure and export). Stamp it back on so the concatenated
#         # frame matches the sheet, and so a table that *does* carry the column
#         # is left exactly as found.
#         if RUN_FOR_COLUMN not in cycle_df.columns:
#             cycle_df = cycle_df.copy()
#             cycle_df[RUN_FOR_COLUMN] = run_for
#         frames.append(cycle_df)
#
#     if not frames:
#         return pd.DataFrame()
#     df = pd.concat(frames, ignore_index=True)
#     return df[usecols] if usecols else df


def _read(spec: Table, usecols: list[str] | None) -> pd.DataFrame:
    """The active backend. Swap for ``_read_sql_table`` to go to production."""
    return _read_excel_table(spec, usecols)


def _descriptive_name_by_code() -> dict[str, str]:
    """``{raw model code: descriptive name}`` from the MEV workbook.

    Read on demand rather than cached: the catalogue is ~20 rows, and a cached
    handle outliving a monkeypatched workbook has bitten this module before.
    """
    try:
        df = _read(table(DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME), None)
    except (FileNotFoundError, ValueError, KeyError):
        return {}
    if "Model Name" not in df.columns or "Model Descriptive Name" not in df.columns:
        return {}
    return {
        str(code).strip(): str(name).strip()
        for code, name in zip(df["Model Name"], df["Model Descriptive Name"])
        if str(code).strip() and str(name).strip()
    }


def _map_model_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Swap portfolio's raw model codes for their descriptive names.

    The descriptive name is the model's identity everywhere above this line --
    ``mev_catalog`` is keyed by it, the metrics store is keyed by it, and it is
    what the Model filter shows. portfolio.xlsx stores the **code**
    (``PD_model_a``), mirroring the production table, so the lookup happens once
    here instead of in each of the half-dozen readers.

    A code with no catalogue entry passes through unchanged rather than being
    dropped -- Loss's portfolio-wide "All Models" has no entry by design, and a
    genuinely unknown code should surface in the filter rather than vanish.
    """
    if MODEL_KEY not in df.columns:
        return df
    lookup = _descriptive_name_by_code()
    if not lookup:
        return df
    df = df.copy()
    df[MODEL_KEY] = df[MODEL_KEY].map(
        lambda value: lookup.get(str(value).strip(), value)
    )
    return df


def read_table(key: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """Read one registered table.

    Raises whatever the backend raises (missing file, missing sheet, ...) so
    each caller keeps its own best-effort handling. Portfolio tables come back
    in the internal column shape -- see
    :func:`shared.domain.reporting_cycle.normalize_portfolio_columns` -- with
    their model codes resolved to descriptive names.
    """
    spec = table(key)
    df = _read(spec, usecols)
    if not spec.normalize:
        return df
    return _map_model_codes(normalize_portfolio_columns(df))


__all__ = ["PORTFOLIO", "MEV", "RULES", "TABLES", "Table", "read_table", "table"]
