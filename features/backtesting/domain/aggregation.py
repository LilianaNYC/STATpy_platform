"""Collapse facility-grain rows to one value per (run key, Quarter).

Pure domain logic: no Dash imports, no I/O. Frames arrive already deduped by
:mod:`features.backtesting.repositories.loader`.

The aggregation rule per metric, and why:

============  ==========================================  ====================
Metric        Rule                                        Formula
============  ==========================================  ====================
``pd``        exposure-weighted, weight = EAD             ``Σ(EAD·PD) / Σ EAD``
``pd_crr``    exposure-weighted, weight = EAD             ``Σ(EAD·PD) / Σ EAD``
``lgd``       exposure-weighted, weight = EAD             ``Σ(EAD·LGD) / Σ EAD``
``ead``       additive                                    ``Σ EAD``
``nco``       additive                                    ``Σ NCO``
============  ==========================================  ====================

**Why rates are exposure-weighted.** A portfolio PD is only meaningful as
expected defaults per unit of exposure. A simple mean gives a $10k facility the
same weight as a $500m one, so the aggregate drifts toward whichever population
is most numerous. Exposure weighting is also the only choice that satisfies the
loss identity: expected defaulted exposure is ``Σ EADᵢ·PDᵢ``, so
``Σ(EAD·PD)/Σ EAD`` is the unique scalar that reproduces the portfolio's total
expected defaulted exposure when multiplied back by total EAD. The same argument
applies to LGD.

**Why the weight is joined, not read.** The PD, PD-CRR and LGD sheets carry no
EAD column, so the weight comes from ``results.ead`` on the run identity
*excluding* ``Model Name`` -- a facility's PD model is not its EAD model. See
:func:`attach_exposure_weights`.

**Coverage is an output, not a footnote.** The join will not always match
everything. Unmatched rows are *dropped*, never equal-weighted -- mixing
weighted and unweighted rows yields a number that is neither and reconciles to
nothing. Dropping is only defensible because every aggregate carries the
coverage figures that say how much was dropped.
"""

from __future__ import annotations

import pandas as pd

from ....shared.domain import constants as config
from . import vintages

__all__ = [
    "EXPOSURE_WEIGHT_COLUMN",
    "ExposureFanOutError",
    "attach_exposure_weights",
    "aggregate_metric",
    "is_exposure_weighted",
]

# Name the joined weight carries once attached. Distinct from the EAD sheet's own
# value column so a frame can hold both without collision.
EXPOSURE_WEIGHT_COLUMN = "Exposure Weight"

# Added by :func:`aggregate_metric` so chart/table code never recomputes them.
TARGET_QUARTER_COLUMN = "Target Quarter"
VINTAGE_QUARTER_COLUMN = "Vintage Quarter"
HORIZON_COLUMN = "Horizon"


class ExposureFanOutError(ValueError):
    """Raised when the EAD side is not unique on the exposure join key."""


def is_exposure_weighted(metric: str) -> bool:
    """Whether ``metric`` is a rate (weighted) rather than an amount (summed)."""
    return metric in config.BACKTESTING_EXPOSURE_WEIGHTED_METRICS


def attach_exposure_weights(
    frame: pd.DataFrame,
    ead_frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Join each row's EAD weight on, returning ``(frame, coverage)``.

    The join key is the run identity **excluding** ``Model Name``, plus the row
    grain -- see :data:`EXPOSURE_JOIN_COLUMNS`.

    ``coverage`` reports what the join achieved:

    ``matched_rows`` / ``total_rows``
        row coverage.
    ``matched_exposure`` / ``total_available_exposure``
        EAD represented by matched metric rows versus all positive EAD available
        in the applied scope.
    ``exposure_coverage``
        matched exposure / total available exposure.
    ``unmatched_rows``
        rows dropped for want of a weight.

    Rows with a null, zero or negative weight are excluded: a non-positive
    weight contributes nothing to a weighted mean and would only distort the
    coverage denominator. Duplicate EAD join keys raise
    :class:`ExposureFanOutError` before the merge can multiply metric rows.
    """
    join_columns = list(config.BACKTESTING_EXPOSURE_JOIN_COLUMNS)
    total_rows = len(frame)
    positive_weights = (
        ead_frame[
            ead_frame[config.BACKTESTING_EAD_VALUE_COLUMN].notna()
            & (ead_frame[config.BACKTESTING_EAD_VALUE_COLUMN] > 0)
        ]
        if not ead_frame.empty
        else ead_frame
    )
    total_available_exposure = (
        float(positive_weights[config.BACKTESTING_EAD_VALUE_COLUMN].sum())
        if not positive_weights.empty
        else 0.0
    )

    if frame.empty or ead_frame.empty:
        # Nothing can be weighted, so nothing survives. Return the frame's own
        # shape plus the weight column so callers can treat the result uniformly.
        empty = frame.iloc[0:0].copy()
        empty[EXPOSURE_WEIGHT_COLUMN] = pd.Series(dtype="float64")
        return empty, {
            "total_rows": total_rows,
            "matched_rows": 0,
            "unmatched_rows": total_rows,
            "matched_exposure": 0.0,
            "total_available_exposure": total_available_exposure,
            "row_coverage": 0.0,
            "exposure_coverage": 0.0,
        }

    weights = (
        ead_frame[join_columns + [config.BACKTESTING_EAD_VALUE_COLUMN]]
        .rename(columns={config.BACKTESTING_EAD_VALUE_COLUMN: EXPOSURE_WEIGHT_COLUMN})
    )

    duplicate_weights = weights.duplicated(join_columns, keep=False)
    if duplicate_weights.any():
        duplicate_key_count = int(
            weights.loc[duplicate_weights, join_columns].drop_duplicates().shape[0]
        )
        raise ExposureFanOutError(
            "exposure join would fan out metric rows: "
            f"{duplicate_key_count} duplicate EAD key(s) on {join_columns!r}"
        )

    merged = frame.merge(weights, on=join_columns, how="left")

    usable = merged[merged[EXPOSURE_WEIGHT_COLUMN].notna() & (merged[EXPOSURE_WEIGHT_COLUMN] > 0)]
    matched_exposure = float(usable[EXPOSURE_WEIGHT_COLUMN].sum()) if not usable.empty else 0.0

    coverage = {
        "total_rows": total_rows,
        "matched_rows": len(usable),
        "unmatched_rows": max(0, total_rows - len(usable)),
        "matched_exposure": matched_exposure,
        "total_available_exposure": total_available_exposure,
        "row_coverage": (len(usable) / total_rows) if total_rows else 0.0,
        "exposure_coverage": (
            matched_exposure / total_available_exposure
            if total_available_exposure > 0
            else 0.0
        ),
    }
    return usable.reset_index(drop=True), coverage


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return None
    return float((values * weights).sum() / total_weight)


def aggregate_metric(
    frame: pd.DataFrame,
    metric: str,
    *,
    ead_frame: pd.DataFrame | None = None,
    group_columns=None,
) -> tuple[pd.DataFrame, dict]:
    """Collapse facility rows to one value per (run key, ``Quarter``).

    Returns ``(aggregated, coverage)``. The aggregated frame carries the run-key
    columns, ``Quarter``, the aggregated ``value``, the contributing
    ``facility_count`` and ``exposure`` (total weight, or the summed amount for
    additive metrics), plus the chart-ready quarter columns added by
    :mod:`.vintages`: ``Vintage Quarter``, ``Target Quarter`` and ``Horizon``.

    ``ead_frame`` is required for exposure-weighted metrics and ignored for
    additive ones. Passing ``group_columns`` overrides the default run-key
    grouping, for callers aggregating to a coarser level (e.g. dropping
    ``Model Name`` to get a segment-level number across both PD populations).
    """
    if group_columns is None:
        group_columns = list(config.backtesting_run_key_columns(metric))
    else:
        group_columns = list(group_columns)

    value_column = config.BACKTESTING_METRIC_VALUE_COLUMNS[metric]
    quarter_column = config.BACKTESTING_QUARTER_COLUMN
    weighted = is_exposure_weighted(metric)

    coverage: dict = {
        "total_rows": len(frame),
        "matched_rows": len(frame),
        "unmatched_rows": 0,
        "matched_exposure": None,
        "total_available_exposure": None,
        "row_coverage": 1.0 if len(frame) else 0.0,
        "exposure_coverage": None,
    }

    if weighted:
        if ead_frame is None:
            raise ValueError(
                f"metric {metric!r} is exposure-weighted; an ead_frame is required to supply the weights"
            )
        frame, coverage = attach_exposure_weights(frame, ead_frame)

    if frame.empty:
        return _empty_aggregate(group_columns), coverage

    grouping = group_columns + [quarter_column]
    rows: list[dict] = []

    for keys, group in frame.groupby(grouping, observed=True, dropna=False):
        record = dict(zip(grouping, keys if isinstance(keys, tuple) else (keys,)))

        if weighted:
            value = _weighted_mean(group[value_column], group[EXPOSURE_WEIGHT_COLUMN])
            exposure = float(group[EXPOSURE_WEIGHT_COLUMN].sum())
        else:
            value = float(group[value_column].sum())
            exposure = value

        record["value"] = value
        record["exposure"] = exposure
        record["facility_count"] = int(len(group))
        rows.append(record)

    aggregated = pd.DataFrame(rows)
    return _attach_quarter_columns(aggregated, group_columns), coverage


def _empty_aggregate(group_columns: list[str]) -> pd.DataFrame:
    columns = group_columns + [
        config.BACKTESTING_QUARTER_COLUMN,
        "value",
        "exposure",
        "facility_count",
        VINTAGE_QUARTER_COLUMN,
        TARGET_QUARTER_COLUMN,
        HORIZON_COLUMN,
    ]
    return pd.DataFrame(columns=columns)


def _attach_quarter_columns(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    """Add ``Vintage Quarter`` / ``Target Quarter`` / ``Horizon``.

    Computed once here so nothing downstream re-derives quarter labels. Labels
    are ``YYYY-Qn`` from :mod:`shared.domain.quarter_labels`, ready to hand to
    ``shared.ui.charts.build_pd_time_series_xaxis`` without adapting.
    """
    snapshot_column = config.BACKTESTING_SNAPSHOT_COLUMN
    quarter_column = config.BACKTESTING_QUARTER_COLUMN

    if frame.empty or snapshot_column not in frame.columns:
        return frame

    frame = frame.copy()
    frame[VINTAGE_QUARTER_COLUMN] = [
        vintages.quarter_label_for_date(value) for value in frame[snapshot_column]
    ]
    frame[TARGET_QUARTER_COLUMN] = [
        vintages.target_quarter_label(snapshot, quarter)
        for snapshot, quarter in zip(frame[snapshot_column], frame[quarter_column])
    ]
    frame[HORIZON_COLUMN] = [
        None if pd.isna(quarter) else int(quarter) for quarter in frame[quarter_column]
    ]

    sort_columns = [column for column in group_columns if column in frame.columns]
    frame = frame.sort_values(sort_columns + [quarter_column], kind="stable")
    return frame.reset_index(drop=True)
