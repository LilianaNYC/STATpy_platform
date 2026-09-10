"""The backtest engine: forecast-vs-actual errors and summary statistics.

Pure domain logic: no Dash imports, no I/O. Consumes the aggregated frames
produced by :mod:`.aggregation`.

How an actual is identified
---------------------------
No sheet carries an actuals column, so the realised outcome is *found* among the
rows rather than read from a dedicated field. ``Quarter == 0`` is the realised
anchor: the observed value at the snapshot date, invariant to ``Scenario`` and
``J/N Flag``. So for target quarter *T*:

* the **actual** is the anchor row of the vintage whose own quarter is *T*;
* every **forecast** of *T* is a row where ``vintage quarter + horizon == T``.

That gives up to one forecast per vintage per target, which is what makes a
"nine forecasts of one quarter" comparison possible.

Two consequences the callers must respect, both of which this module encodes
rather than hides:

* **The most recent horizons have no actual yet.** No vintage has reached them.
  :func:`build_error_records` simply produces no record for those targets, and
  :func:`unmatched_forecast_count` reports how many forecasts were left
  unscored so a chart can render them as forecast-only rather than as zero
  error.
* **Only the base scenario is scored.** Non-baseline scenarios are deliberately
  conservative, so scoring them against realised outcomes measures the
  conservatism buffer, not model accuracy. :func:`build_error_records` always
  filters both forecasts and actual anchors to ``BACKTESTING_BASE_SCENARIO``.

Error definitions
-----------------
For forecast *f* and actual *a*:

* ``error``            = ``f - a``   (signed; positive = over-forecast)
* ``absolute_error``   = ``|f - a|``
* ``percentage_error`` = ``(f - a) / a``  (``None`` when ``a == 0``)

Summary statistics over a set of records:

* ``bias``      -- mean signed error. The sign is the point: a negative bias on a
  loss metric means losses were systematically under-forecast.
* ``mae``       -- mean absolute error.
* ``rmse``      -- root mean squared error; penalises large misses more than
  ``mae``, so ``rmse >> mae`` indicates a few big misses rather than uniform drift.
* ``mape``      -- mean absolute percentage error, over records with a non-zero
  actual only (its denominator count is reported separately as ``mape_count``).
* ``hit_rate``  -- share of records whose absolute percentage error is within
  ``tolerance``. Scale-free, so it is comparable across metrics.
"""

from __future__ import annotations

import math

import pandas as pd

from ....shared.domain import constants as config
from ....shared.domain.calculations import is_finite_number
from . import aggregation, vintages

__all__ = [
    "DEFAULT_HIT_RATE_TOLERANCE",
    "build_actual_lookup",
    "build_error_records",
    "unmatched_forecast_count",
    "summarize_errors",
    "summarize_by",
    "error_records_to_chart_rows",
]

# Within +/-10% of the realised value counts as a hit unless a caller says
# otherwise. Expressed as a fraction, matching ``percentage_error``.
DEFAULT_HIT_RATE_TOLERANCE = 0.10

# Columns on an aggregated frame (see :mod:`.aggregation`).
_TARGET = aggregation.TARGET_QUARTER_COLUMN
_VINTAGE = aggregation.VINTAGE_QUARTER_COLUMN
_HORIZON = aggregation.HORIZON_COLUMN


def _actual_key(row, key_columns: list[str]) -> tuple:
    return tuple(row[column] for column in key_columns)


def build_actual_lookup(
    aggregated: pd.DataFrame,
    *,
    key_columns=None,
) -> dict[tuple, float]:
    """Map ``(*key, target quarter)`` to the realised value at that quarter.

    ``key_columns`` names the population identity an actual is scoped to. By
    default that is Segment Name: segments must never borrow one another's
    actuals, while model/run/scenario filters are expected to have been applied
    by the caller.
    """
    if key_columns is None:
        key_columns = [config.BACKTESTING_SEGMENT_COLUMN]
    key_columns = list(key_columns)

    if aggregated.empty:
        return {}

    quarter_column = config.BACKTESTING_QUARTER_COLUMN
    anchors = aggregated[
        aggregated[quarter_column].map(lambda value: vintages.is_anchor_quarter(_as_int(value)))
    ]

    lookup: dict[tuple, float] = {}
    for _, row in anchors.iterrows():
        value = row["value"]
        if not is_finite_number(value):
            continue
        key = _actual_key(row, key_columns) + (row[_TARGET],)
        lookup[key] = float(value)
    return lookup


def _as_int(value) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_error_records(
    aggregated: pd.DataFrame,
    *,
    scenario=config.BACKTESTING_BASE_SCENARIO,
    key_columns=None,
    carry_columns=None,
) -> list[dict]:
    """One record per (vintage, target quarter, horizon) that has an actual.

    Each record carries the identity columns, the quarter labels, ``forecast``,
    ``actual``, and the three error measures. Forecasts whose target has no
    realised anchor yet are omitted -- see :func:`unmatched_forecast_count`.

    ``carry_columns`` names extra identity columns to copy onto each record (for
    example ``J/N Flag`` or ``Model Name``) so callers can group by them later
    without re-joining.
    """
    if aggregated.empty:
        return []

    if key_columns is None:
        key_columns = [config.BACKTESTING_SEGMENT_COLUMN]
    key_columns = list(key_columns)

    quarter_column = config.BACKTESTING_QUARTER_COLUMN

    scoped = aggregated
    scenario_column = config.BACKTESTING_SCENARIO_COLUMN
    if scenario is not None and scenario_column in scoped.columns:
        scoped = scoped[scoped[scenario_column] == scenario]
    lookup = build_actual_lookup(scoped, key_columns=key_columns)

    # Anchors are the actuals themselves; scoring one against itself is a
    # tautology that would flatter every summary statistic.
    forecasts = scoped[
        scoped[quarter_column].map(lambda value: not vintages.is_anchor_quarter(_as_int(value)))
    ]

    default_carry = [
        column
        for column in (
            config.BACKTESTING_MODEL_NAME_COLUMN,
            config.BACKTESTING_RUN_FOR_COLUMN,
            config.BACKTESTING_SCENARIO_COLUMN,
            config.BACKTESTING_JN_FLAG_COLUMN,
        )
        if column in aggregated.columns
    ]
    carry = list(carry_columns) if carry_columns is not None else default_carry

    records: list[dict] = []
    for _, row in forecasts.iterrows():
        target = row[_TARGET]
        actual = lookup.get(_actual_key(row, key_columns) + (target,))
        forecast = row["value"]
        if actual is None or not is_finite_number(forecast):
            continue

        error = float(forecast) - actual
        record = {
            **{column: row[column] for column in key_columns},
            **{column: row[column] for column in carry if column in row.index},
            "vintage_quarter": row[_VINTAGE],
            "target_quarter": target,
            "horizon": _as_int(row[_HORIZON]),
            # ``quarter`` is the chart-facing label: shared/ui/charts.py trend
            # builders read row["quarter"], and a backtest is plotted against the
            # quarter being forecast rather than the vintage.
            "quarter": target,
            "forecast": float(forecast),
            "actual": actual,
            "error": error,
            "absolute_error": abs(error),
            "percentage_error": (error / actual) if actual else None,
            "exposure": float(row["exposure"]) if is_finite_number(row.get("exposure")) else None,
            "facility_count": row.get("facility_count"),
        }
        records.append(record)

    records.sort(
        key=lambda record: (
            vintages.quarter_sort_key(record["vintage_quarter"]),
            record["horizon"] if record["horizon"] is not None else -1,
        )
    )
    return records


def unmatched_forecast_count(
    aggregated: pd.DataFrame,
    *,
    scenario=config.BACKTESTING_BASE_SCENARIO,
    key_columns=None,
) -> int:
    """Forecast rows whose target quarter has no realised anchor yet.

    Not an error condition: the most recent horizons genuinely have no actual.
    Surfacing the count lets a caller render those points as forecast-only
    instead of silently dropping them, which would misrepresent the horizon.
    """
    if aggregated.empty:
        return 0

    if key_columns is None:
        key_columns = [config.BACKTESTING_SEGMENT_COLUMN]
    key_columns = list(key_columns)

    quarter_column = config.BACKTESTING_QUARTER_COLUMN
    scoped = aggregated
    scenario_column = config.BACKTESTING_SCENARIO_COLUMN
    if scenario is not None and scenario_column in scoped.columns:
        scoped = scoped[scoped[scenario_column] == scenario]
    lookup = build_actual_lookup(scoped, key_columns=key_columns)
    forecasts = scoped[
        scoped[quarter_column].map(lambda value: not vintages.is_anchor_quarter(_as_int(value)))
    ]

    unmatched = 0
    for _, row in forecasts.iterrows():
        if lookup.get(_actual_key(row, key_columns) + (row[_TARGET],)) is None:
            unmatched += 1
    return unmatched


def summarize_errors(
    records,
    *,
    tolerance: float = DEFAULT_HIT_RATE_TOLERANCE,
) -> dict:
    """Summary statistics over a set of error records.

    Returns ``count``, ``bias``, ``mae``, ``rmse``, ``mape``, ``mape_count`` and
    ``hit_rate``. Every statistic is ``None`` when it has nothing to measure, so
    a caller can distinguish "no data" from "zero error" -- a distinction a
    ``0.0`` default would destroy.
    """
    records = list(records)
    errors = [record["error"] for record in records if is_finite_number(record.get("error"))]
    percentages = [
        record["percentage_error"]
        for record in records
        if is_finite_number(record.get("percentage_error"))
    ]

    count = len(errors)
    if not count:
        return {
            "count": 0,
            "bias": None,
            "mae": None,
            "rmse": None,
            "mape": None,
            "mape_count": 0,
            "hit_rate": None,
        }

    absolute = [abs(value) for value in errors]
    return {
        "count": count,
        "bias": sum(errors) / count,
        "mae": sum(absolute) / count,
        "rmse": math.sqrt(sum(value * value for value in errors) / count),
        "mape": (sum(abs(value) for value in percentages) / len(percentages)) if percentages else None,
        "mape_count": len(percentages),
        "hit_rate": (
            sum(1 for value in percentages if abs(value) <= tolerance) / len(percentages)
            if percentages
            else None
        ),
    }


def summarize_by(
    records,
    group_keys,
    *,
    tolerance: float = DEFAULT_HIT_RATE_TOLERANCE,
) -> list[dict]:
    """Summary statistics at an arbitrary grouping level.

    ``group_keys`` is any sequence of record keys -- ``["horizon"]`` for an
    error-by-horizon curve, ``["Segment Name"]`` to rank segments,
    ``["J/N Flag", "horizon"]`` to compare judgemental against non-judgemental
    across the horizon, and so on. Groups come back sorted by their key, with the
    grouping values merged into each summary so the result is directly
    renderable.
    """
    group_keys = list(group_keys)
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        key = tuple(record.get(name) for name in group_keys)
        grouped.setdefault(key, []).append(record)

    summaries = []
    for key, group in grouped.items():
        summary = dict(zip(group_keys, key))
        summary.update(summarize_errors(group, tolerance=tolerance))
        summaries.append(summary)

    summaries.sort(key=lambda summary: tuple(
        _sort_value(summary.get(name)) for name in group_keys
    ))
    return summaries


def _sort_value(value):
    """Sort key that keeps ``None`` first and mixed types comparable."""
    if value is None:
        return (0, 0.0, "")
    if isinstance(value, bool):
        return (1, float(value), "")
    if isinstance(value, (int, float)):
        return (1, float(value), "")
    return (2, 0.0, str(value))


def error_records_to_chart_rows(records, *, value_key: str = "error") -> list[dict]:
    """Reshape error records into the row shape the shared trend builders read.

    ``shared/ui/charts.py``'s trend builders consume a list of dicts keyed by
    ``"quarter"`` holding a ``YYYY-Qn`` label (``build_pd_time_series_xaxis``
    renders those compactly as ``YYYYQn``). Records from
    :func:`build_error_records` already carry ``quarter``, so this only selects
    and orders them -- no adapter is needed at the chart milestone.

    ``value_key`` picks which measure becomes the plotted series: ``"error"``,
    ``"absolute_error"``, ``"percentage_error"``, ``"forecast"`` or ``"actual"``.
    """
    rows = [
        {
            "quarter": record["quarter"],
            "vintage_quarter": record["vintage_quarter"],
            "horizon": record["horizon"],
            "value": record.get(value_key),
            "forecast": record.get("forecast"),
            "actual": record.get("actual"),
        }
        for record in records
        if record.get("quarter")
    ]
    rows.sort(key=lambda row: vintages.quarter_sort_key(row["quarter"]))
    return rows
