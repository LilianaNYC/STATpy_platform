"""Model use case / reporting cycle column shapes.

Both workbooks carry the composite cycle value and both of its parts, under the
same three column names -- ``portfolio.xlsx`` (every sheet) and
``dummy_mev_data.xlsx``'s ``model_names`` sheet:

================  ==============================================
``Run For``       the composite, e.g. "CCAR 2026" / "CECL 2025Q1"
``Model Use Case`` the use case, e.g. "ST - CCAR" / "CECL"
``Reporting Cycle`` the bare cycle, e.g. "2026" / "2025Q1"
================  ==============================================

Internally, though, ``reporting_cycle`` has always meant the **composite** -- it
is the join key behind every store, figure, export and Dash element ID in both
dashboards. Rather than rename that key everywhere, portfolio frames are swapped
into the internal shape the moment they are read, by
:func:`normalize_portfolio_columns`: ``Run For`` becomes ``reporting_cycle`` and
the workbook's ``Reporting Cycle`` becomes ``cycle``. Downstream code therefore
sees exactly what it saw before the workbooks gained the split columns.

Only portfolio frames are normalized. The MEV workbook's ``model_names`` and
``scenario`` sheets also have a ``Run For`` column, but their readers use it
under that name, so normalizing them would silently rename a column those
callers rely on -- hence callers opt in rather than the rename triggering off a
column name.

This module is pure: no I/O, no Dash.
"""

from __future__ import annotations

import pandas as pd

from .constants import (
    COHORT_QUARTER_KEY,
    CYCLE_KEY,
    MONITORING_POINT_COLUMN,
    METRICS_MODEL_COLUMN,
    METRICS_QUARTER_COLUMN,
    METRICS_SEGMENT_COLUMN,
    MODEL_KEY,
    QUARTER_KEY,
    REPORTING_CYCLE_COLUMN,
    REPORTING_CYCLE_KEY,
    RUN_FOR_COLUMN,
    SEGMENT_KEY,
)

# Workbook column -> internal frame key. ``Run For`` carries the composite, which
# internally is ``reporting_cycle``; the workbook's own ``Reporting Cycle`` (the
# bare cycle) therefore lands on ``cycle``. The grain columns are a plain
# case-fold. Applied in one pass, so ``Reporting Cycle`` and ``Run For`` never
# collide on the way through.
_PORTFOLIO_COLUMN_MAP = {
    RUN_FOR_COLUMN: REPORTING_CYCLE_KEY,
    REPORTING_CYCLE_COLUMN: CYCLE_KEY,
    METRICS_QUARTER_COLUMN: QUARTER_KEY,
    METRICS_MODEL_COLUMN: MODEL_KEY,
    METRICS_SEGMENT_COLUMN: SEGMENT_KEY,
}


def normalize_portfolio_columns(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Swap a **portfolio** frame into the internal column shape.

    Maps every column in :data:`_PORTFOLIO_COLUMN_MAP` that the frame actually
    has, in a single pass. Columns that are absent are simply skipped, so sheets
    that predate any of these renames still load.

    Do not call this on MEV-workbook frames -- see the module docstring.
    """
    if df is None:
        return df

    renames = {old: new for old, new in _PORTFOLIO_COLUMN_MAP.items() if old in df.columns}
    df = df.rename(columns=renames) if renames else df
    return _promote_monitoring_point(df)


def _promote_monitoring_point(df: pd.DataFrame) -> pd.DataFrame:
    """Make ``quarter`` mean the **as-of** date on every portfolio frame.

    PD's metrics sheet distinguishes the two: ``monitoring_point`` is the as-of
    and ``Quarter`` is the *cohort start*, which sits one year back for 1y and
    nco_1y rows and two years back for 2y rows -- so one monitoring point spans
    three different quarters. Every other sheet has no ``horizon``, so its
    ``Quarter`` is already the as-of.

    Rather than teach each of the half-dozen readers that difference, the swap
    happens once here, at the read seam: ``quarter`` becomes the as-of
    everywhere and the cohort start stays available as ``cohort_quarter``. The
    monitoring-point filter, the metrics store and every trend therefore keep
    the exact keys they had before PD gained the column.
    """
    if MONITORING_POINT_COLUMN not in df.columns:
        return df
    df = df.rename(columns={QUARTER_KEY: COHORT_QUARTER_KEY}) if QUARTER_KEY in df.columns else df
    df[QUARTER_KEY] = df[MONITORING_POINT_COLUMN]
    return df


__all__ = ["normalize_portfolio_columns"]
