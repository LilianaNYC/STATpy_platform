"""Pure diagnostic datasets for the backtesting dashboard."""

from __future__ import annotations

from itertools import permutations

from ....shared.domain import constants as config
from ....shared.domain.calculations import is_finite_number
from . import errors, vintages

METRIC_LABELS = {
    config.BACKTESTING_METRIC_PD: "PD",
    config.BACKTESTING_METRIC_PD_CRR: "PD CRR",
    config.BACKTESTING_METRIC_LGD: "LGD",
    config.BACKTESTING_METRIC_EAD: "EAD",
    config.BACKTESTING_METRIC_NCO: "NCO",
}


def build_scorecard_rows(views: dict[str, dict]) -> list[dict]:
    """One governed accuracy row per metric."""
    rows = []
    for metric in config.BACKTESTING_METRIC_SHEETS:
        view = views.get(metric) or {}
        summary = view.get("summary") or {}
        coverage = view.get("coverage") or {}
        rows.append({
            "metric": metric,
            "label": METRIC_LABELS.get(metric, metric.upper()),
            "count": summary.get("count", 0),
            "percentage_bias": summary.get("percentage_bias"),
            "mae": summary.get("mae"),
            "rmse": summary.get("rmse"),
            "mape": summary.get("mape"),
            "mape_count": summary.get("mape_count", 0),
            "hit_rate": summary.get("hit_rate"),
            "rag": summary.get("rag", "N/A"),
            "row_coverage": coverage.get("row_coverage"),
            "exposure_coverage": coverage.get("exposure_coverage"),
        })
    return rows


def build_cross_metric_horizon_rows(views: dict[str, dict]) -> list[dict]:
    rows = []
    for metric in config.BACKTESTING_METRIC_SHEETS:
        for summary in (views.get(metric) or {}).get("by_horizon") or []:
            rows.append({
                **summary,
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric.upper()),
            })
    return rows


def build_error_matrix(records, row_key: str) -> dict:
    """Aggregate signed percentage error into a row × horizon matrix."""
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        row_value = record.get(row_key)
        horizon = record.get("horizon")
        if row_value is None or horizon is None:
            continue
        grouped.setdefault((row_value, int(horizon)), []).append(record)

    cells = []
    for (row_value, horizon), group in grouped.items():
        percentages = [
            float(record["percentage_error"])
            for record in group
            if is_finite_number(record.get("percentage_error"))
        ]
        if not percentages:
            continue
        absolute_errors = [
            float(record["absolute_error"])
            for record in group
            if is_finite_number(record.get("absolute_error"))
        ]
        coverage_values = [
            float(record["coverage"])
            for record in group
            if is_finite_number(record.get("coverage"))
        ]
        cells.append({
            "row": row_value,
            "horizon": horizon,
            "signed_error": sum(percentages) / len(percentages),
            "mape": sum(abs(value) for value in percentages) / len(percentages),
            "mae": sum(absolute_errors) / len(absolute_errors) if absolute_errors else None,
            "count": len(percentages),
            "coverage": (
                sum(coverage_values) / len(coverage_values) if coverage_values else None
            ),
            "target_quarters": sorted({
                record.get("target_quarter") for record in group
                if record.get("target_quarter")
            }, key=vintages.quarter_sort_key),
        })

    if row_key == "vintage_quarter":
        row_values = sorted({cell["row"] for cell in cells}, key=vintages.quarter_sort_key)
    else:
        row_values = sorted({str(cell["row"]) for cell in cells})
    horizons = sorted({cell["horizon"] for cell in cells})
    limit = max(
        config.BACKTESTING_RAG_GREEN_MAX_MAPE,
        max((abs(cell["signed_error"]) for cell in cells), default=0.0),
    )
    return {"rows": row_values, "horizons": horizons, "cells": cells, "limit": limit}


def build_revision_series(records) -> dict:
    """Successive forecasts of the latest target quarter with two revisions."""
    by_target: dict[str, list[dict]] = {}
    for record in records:
        if record.get("target_quarter") and record.get("vintage_quarter"):
            by_target.setdefault(record["target_quarter"], []).append(record)
    candidates = [
        target for target, group in by_target.items()
        if len({record["vintage_quarter"] for record in group}) >= 2
    ]
    if not candidates:
        return {"target_quarter": None, "actual": None, "series": []}
    target = max(candidates, key=vintages.quarter_sort_key)
    grouped: dict[str, dict[str, list[float]]] = {}
    actuals = []
    for record in by_target[target]:
        cycle = str(record.get(config.BACKTESTING_RUN_FOR_COLUMN) or "Cycle")
        grouped.setdefault(cycle, {}).setdefault(record["vintage_quarter"], []).append(
            float(record["forecast"])
        )
        if is_finite_number(record.get("actual")):
            actuals.append(float(record["actual"]))
    series = []
    for cycle, vintages_by_cycle in sorted(grouped.items()):
        points = [
            {"vintage": vintage, "forecast": sum(values) / len(values)}
            for vintage, values in vintages_by_cycle.items()
        ]
        points.sort(key=lambda point: vintages.quarter_sort_key(point["vintage"]))
        series.append({"cycle": cycle, "points": points})
    return {
        "target_quarter": target,
        "actual": sum(actuals) / len(actuals) if actuals else None,
        "series": series,
    }


def shapley_product_attribution(actual, forecast) -> tuple[float, float, float]:
    """Order-independent PD/LGD/EAD contributions to a product change."""
    actual = tuple(float(value) for value in actual)
    forecast = tuple(float(value) for value in forecast)
    contributions = [0.0, 0.0, 0.0]
    for order in permutations(range(3)):
        state = list(actual)
        previous = state[0] * state[1] * state[2]
        for index in order:
            state[index] = forecast[index]
            current = state[0] * state[1] * state[2]
            contributions[index] += current - previous
            previous = current
    return tuple(value / 6.0 for value in contributions)


def _record_key(record: dict) -> tuple:
    return (
        record.get("vintage_quarter"),
        record.get("target_quarter"),
        record.get("horizon"),
        record.get(config.BACKTESTING_RUN_FOR_COLUMN),
    )


def _single_record_index(records) -> dict[tuple, dict]:
    return {_record_key(record): record for record in records}


def _combined_pd_index(records) -> dict[tuple, dict]:
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        grouped.setdefault(_record_key(record), []).append(record)
    combined = {}
    for key, group in grouped.items():
        weights = [
            float(record.get("exposure") or 0.0)
            if is_finite_number(record.get("exposure")) else 0.0
            for record in group
        ]
        total = sum(weights)
        if total <= 0:
            weights = [1.0] * len(group)
            total = float(len(group))
        combined[key] = {
            "forecast": sum(float(record["forecast"]) * weight for record, weight in zip(group, weights)) / total,
            "actual": sum(float(record["actual"]) * weight for record, weight in zip(group, weights)) / total,
        }
    return combined


def build_nco_attribution(
    nco_records,
    pd_records,
    lgd_records,
    ead_records,
) -> dict:
    """Mean NCO error decomposed into PD, LGD, EAD and reconciliation residual."""
    nco_index = _single_record_index(nco_records)
    pd_index = _combined_pd_index(pd_records)
    lgd_index = _single_record_index(lgd_records)
    ead_index = _single_record_index(ead_records)
    common = sorted(set(nco_index) & set(pd_index) & set(lgd_index) & set(ead_index))
    totals = [0.0, 0.0, 0.0]
    residual = 0.0
    for key in common:
        nco = nco_index[key]
        actual = (pd_index[key]["actual"], lgd_index[key]["actual"], ead_index[key]["actual"])
        forecast = (
            pd_index[key]["forecast"], lgd_index[key]["forecast"], ead_index[key]["forecast"]
        )
        parts = shapley_product_attribution(actual, forecast)
        for index, value in enumerate(parts):
            totals[index] += value
        residual += float(nco["error"]) - sum(parts)
    count = len(common)
    if count:
        totals = [value / count for value in totals]
        residual /= count
    values = totals + [residual]
    return {
        "labels": ["PD", "LGD", "EAD", "Reconciliation residual"],
        "values": values,
        "total_error": sum(values),
        "count": count,
        "coverage": count / len(nco_index) if nco_index else 0.0,
        "basis": "Mean error across comparable vintages, horizons, and cycles",
    }
