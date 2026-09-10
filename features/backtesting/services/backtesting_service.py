"""Orchestration for the backtesting dashboard.

Turns an applied filter scope into everything a metric section needs to render:
the aggregated series, the forecast-versus-actual error records, and the
by-horizon summary. Callbacks call this and hand the result straight to the
view; no heavy logic lives in the callback layer.

The order of operations is fixed and matters (see ``docs/backtesting_plan.md``
section 1):

    scope the rows -> aggregate results.ead -> attach exposure weights
    -> aggregate the rate metrics -> build error records -> summarise

Scoping note: the Model filter is **PD-side** (it lists PD models). Applying it
to ``results.lgd`` or ``results.ead`` by ``Model Name`` would match nothing --
those sheets name LGD and EAD models. So a model selection is translated into
the *facility population* that PD model covers, and the other sheets are scoped
to those facilities instead. That keeps every metric section describing the same
book.
"""

from __future__ import annotations

import pandas as pd

from ....shared.domain import constants as config
from ..data_access import BACKTESTING_PAGE_DATA
from ..domain import aggregation, errors, selectors

__all__ = [
    "build_metric_view",
    "build_dashboard_view",
    "build_loss_curve_series",
    "build_cumulative_loss_series",
]

_SEGMENT = config.BACKTESTING_SEGMENT_COLUMN
_MODEL = config.BACKTESTING_MODEL_NAME_COLUMN
_PD_MODEL = config.BACKTESTING_PD_MODEL_NAME_COLUMN
_RUN_FOR = config.BACKTESTING_RUN_FOR_COLUMN
_SCENARIO = config.BACKTESTING_SCENARIO_COLUMN
_JN = config.BACKTESTING_JN_FLAG_COLUMN
_SNAPSHOT = config.BACKTESTING_SNAPSHOT_COLUMN
_FACILITY = config.BACKTESTING_FACILITY_ID_COLUMN
_INSTRUMENT = config.BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN

def _frame(metric: str) -> pd.DataFrame:
    return (BACKTESTING_PAGE_DATA.get("metrics") or {}).get(metric, pd.DataFrame())


def _scoped_models(applied: dict) -> list[str]:
    """PD models surviving the Region / Portfolio / Model Group / Model picks."""
    model = applied.get("model")
    if not selectors.is_all(model):
        return [model]
    return selectors.models_matching(
        region=applied.get("region"),
        portfolio=applied.get("portfolio"),
        model_group=applied.get("model_group"),
        segment=applied.get("segment"),
    )


def _facility_scope(applied: dict) -> set[tuple[str, str]] | None:
    """Facility x instrument pairs covered by the scoped PD models.

    ``None`` means "no restriction". Used to scope LGD/EAD/NCO by population
    rather than by a model name they do not carry.
    """
    models = set(_scoped_models(applied))
    if not models or models == set(selectors.all_models()):
        return None

    pairs: set[tuple[str, str]] = set()
    for metric in config.BACKTESTING_PD_METRICS:
        frame = _frame(metric)
        if frame.empty or _MODEL not in frame.columns:
            continue
        scoped = frame[frame[_MODEL].isin(models)]
        if scoped.empty:
            continue
        pairs |= set(map(tuple, scoped[[_FACILITY, _INSTRUMENT]].drop_duplicates().to_numpy()))
    return pairs or None


def _apply_scope(
    frame: pd.DataFrame,
    applied: dict,
    *,
    model_column: str | None,
    facility_pairs: set[tuple[str, str]] | None,
) -> pd.DataFrame:
    """Filter one metric frame down to the applied scope."""
    if frame.empty:
        return frame

    scoped = frame
    segment = applied.get("segment")
    if not selectors.is_all(segment):
        scoped = scoped[scoped[_SEGMENT] == segment]

    for column, key in ((_RUN_FOR, "run_for"), (_SCENARIO, "scenario"), (_JN, "jn_flag")):
        value = applied.get(key)
        if not selectors.is_all(value):
            scoped = scoped[scoped[column] == value]

    snapshot = applied.get("snapshot")
    if not selectors.is_all(snapshot):
        scoped = scoped[scoped[_SNAPSHOT].astype("datetime64[ns]") == pd.Timestamp(snapshot)]

    if model_column and model_column in scoped.columns:
        models = _scoped_models(applied)
        if models and set(models) != set(selectors.all_models()):
            scoped = scoped[scoped[model_column].isin(models)]
    elif facility_pairs is not None:
        index = pd.MultiIndex.from_frame(scoped[[_FACILITY, _INSTRUMENT]])
        scoped = scoped[index.isin(facility_pairs)]

    return scoped


def _model_column_for(metric: str) -> str | None:
    """Which column a PD-model selection filters on, if any.

    ``None`` means the metric has no PD-model column, so a model selection is
    applied as a facility-population restriction instead.
    """
    if metric in config.BACKTESTING_PD_METRICS:
        return _MODEL
    if metric == config.BACKTESTING_METRIC_NCO:
        return _PD_MODEL
    return None


def _vintage_series(scoped: pd.DataFrame, metric: str, ead_frame, scenario: str) -> list[dict]:
    """One projection path per vintage: value at each horizon.

    This is the vintage-curve view -- every Month End Snapshot aligned at
    horizon 0 so cohorts can be compared against each other by *age* rather
    than by calendar quarter. Population dimensions combine, while cycle and J/N
    remain in the key so alternative runs never inflate an amount.

    Unlike the error records, this keeps **every** horizon, including the recent
    ones with no realised outcome yet: a vintage curve is about the projected
    path, not about what has been scored.
    """
    if scoped.empty:
        return []

    scoped = scoped[scoped[_SCENARIO] == scenario]
    if scoped.empty:
        return []
    if ead_frame is not None and not ead_frame.empty:
        ead_frame = ead_frame[ead_frame[_SCENARIO] == scenario]

    aggregated, _ = aggregation.aggregate_metric(
        scoped,
        metric,
        ead_frame=ead_frame,
        group_columns=[_SNAPSHOT],
    )
    if aggregated.empty:
        return []

    series: dict[str, list[dict]] = {}
    for _, row in aggregated.iterrows():
        horizon = row[aggregation.HORIZON_COLUMN]
        if horizon is None:
            continue
        vintage = row[aggregation.VINTAGE_QUARTER_COLUMN]
        series.setdefault(vintage, []).append({
            "horizon": int(horizon),
            "value": row["value"],
            "exposure": row["exposure"],
            "target_quarter": row[aggregation.TARGET_QUARTER_COLUMN],
        })

    return [
        {
            "vintage": vintage,
            "points": sorted(points, key=lambda point: point["horizon"]),
        }
        for vintage, points in sorted(series.items(), key=lambda item: item[0])
    ]


def build_loss_curve_series(applied: dict | None, *, cumulative: bool = True) -> list[dict]:
    """Net charge-off as a share of the vintage's opening exposure, by age.

    The static-pool view: each vintage's losses divided by its exposure at
    horizon 0, so cohorts of different sizes are directly comparable, plotted
    against age rather than calendar quarter.

    ``cumulative=True`` accumulates losses through horizon *h* -- the shape used
    for static-pool reporting, which answers "how much has this cohort lost in
    total by this age".

    ``cumulative=False`` gives the loss *in* each quarter. Same denominator, so
    the two are directly comparable, but it answers a different question: when
    losses arrive. A cumulative curve can only ever rise, so it hides the timing
    of the peak -- two cohorts ending at the same total can have very different
    periodic profiles.
    """
    applied = applied or {}
    scenario = applied.get("scenario")
    scenario = config.BACKTESTING_BASE_SCENARIO if selectors.is_all(scenario) else scenario

    facility_pairs = _facility_scope(applied)
    nco = _apply_scope(
        _frame(config.BACKTESTING_METRIC_NCO), applied,
        model_column=_PD_MODEL, facility_pairs=facility_pairs,
    )
    ead = _apply_scope(
        _frame(config.BACKTESTING_METRIC_EAD), applied,
        model_column=None, facility_pairs=facility_pairs,
    )
    if nco.empty or ead.empty:
        return []

    nco_series = _vintage_series(nco, config.BACKTESTING_METRIC_NCO, None, scenario)
    ead_series = _vintage_series(ead, config.BACKTESTING_METRIC_EAD, None, scenario)

    opening = {}
    for entry in ead_series:
        first = next(
            (point for point in entry["points"]
             if point["horizon"] == config.BACKTESTING_ANCHOR_QUARTER),
            None,
        )
        if first and first["value"]:
            opening[entry["vintage"]] = float(first["value"])

    curves = []
    for entry in nco_series:
        balance = opening.get(entry["vintage"])
        if not balance:
            continue
        running = 0.0
        points = []
        for point in entry["points"]:
            loss = float(point["value"] or 0.0)
            running += loss
            points.append({
                "horizon": point["horizon"],
                "value": (running if cumulative else loss) / balance,
                "target_quarter": point["target_quarter"],
            })
        if points:
            curves.append({"vintage": entry["vintage"], "points": points})
    return curves


def build_cumulative_loss_series(applied: dict | None) -> list[dict]:
    """Cumulative loss curves (see :func:`build_loss_curve_series`)."""
    return build_loss_curve_series(applied, cumulative=True)


def build_metric_view(metric: str, applied: dict | None) -> dict:
    """Everything one metric section needs, for the applied scope.

    Returns ``records`` (forecast-versus-actual), ``by_horizon`` summaries,
    ``summary`` (overall), ``coverage`` from the exposure join, ``unscored``
    (forecasts whose target has no realised anchor yet), and ``row_count``.
    """
    applied = applied or {}
    empty = {
        "metric": metric,
        "records": [],
        "vintage_series": [],
        "by_horizon": [],
        "summary": errors.summarize_errors([]),
        "coverage": None,
        "unscored": 0,
        "row_count": 0,
    }

    frame = _frame(metric)
    if frame.empty:
        return empty

    facility_pairs = _facility_scope(applied)
    scoped = _apply_scope(
        frame, applied, model_column=_model_column_for(metric), facility_pairs=facility_pairs
    )
    if scoped.empty:
        return empty

    ead_frame = None
    if aggregation.is_exposure_weighted(metric):
        # The weights must be scoped identically, or the aggregate would be
        # weighted by exposure from outside the selection.
        ead_frame = _apply_scope(
            _frame(config.BACKTESTING_METRIC_EAD),
            applied,
            model_column=None,
            facility_pairs=facility_pairs,
        )

    aggregated, coverage = aggregation.aggregate_metric(
        scoped,
        metric,
        ead_frame=ead_frame,
    )
    if aggregated.empty:
        return {**empty, "coverage": coverage, "row_count": len(scoped)}

    scenario = applied.get("scenario")
    scenario = (
        config.BACKTESTING_BASE_SCENARIO
        if selectors.is_all(scenario)
        else scenario
    )
    records = errors.build_error_records(aggregated, scenario=scenario)
    return {
        "metric": metric,
        "vintage_series": _vintage_series(scoped, metric, ead_frame, scenario),
        "records": records,
        "by_horizon": errors.summarize_by(records, ["horizon"]),
        "summary": errors.summarize_errors(records),
        "coverage": coverage,
        "unscored": errors.unmatched_forecast_count(aggregated, scenario=scenario),
        "row_count": len(scoped),
    }


def build_dashboard_view(applied: dict | None) -> dict[str, dict]:
    """One view per metric, keyed by metric."""
    return {
        metric: build_metric_view(metric, applied)
        for metric in config.BACKTESTING_METRIC_SHEETS
    }
