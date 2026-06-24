"""EAD performance data preparation.

The EAD page follows the same 1 year monitoring flow as the LGD page: ME and
RMSE feed Calibration Conservatism, Kendall's Tau feeds Discriminatory Power,
and the worst dimension RAG becomes the Performance RAG.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from . import constants as config
from .calculations import calculate_pd_metric_rag, get_worst_pd_rag, pd_rag_score

EAD_METRICS = ["ME", "RMSE", "Kendall's Tau"]
EAD_CALIBRATION_METRICS = ["ME", "RMSE"]
EAD_DISCRIMINATION_METRICS = ["Kendall's Tau"]
EAD_ALL_MODELS_LABEL = "All models"


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _quarter_sort_key(value: str) -> tuple[int, int]:
    text = str(value or "")
    try:
        year, quarter = text.split("Q", 1)
        return int(year), int(quarter)
    except (TypeError, ValueError):
        return 0, 0


def _mean(values: list[float]) -> float | None:
    clean = [float(value) for value in values if _is_finite(value)]
    return sum(clean) / len(clean) if clean else None


def _kendall_tau(x_values: list[float], y_values: list[float]) -> float | None:
    pairs = [
        (float(x), float(y))
        for x, y in zip(x_values, y_values)
        if _is_finite(x) and _is_finite(y)
    ]
    if len(pairs) < 2:
        return None
    if len({x for x, _ in pairs}) < 2 or len({y for _, y in pairs}) < 2:
        return None

    concordant = 0
    discordant = 0
    ties_x = 0
    ties_y = 0
    for index, (x_i, y_i) in enumerate(pairs[:-1]):
        for x_j, y_j in pairs[index + 1:]:
            dx = (x_i > x_j) - (x_i < x_j)
            dy = (y_i > y_j) - (y_i < y_j)
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            elif dx == 0 and dy != 0:
                ties_x += 1
            elif dy == 0 and dx != 0:
                ties_y += 1

    denominator = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def get_ead_thresholds(data: dict) -> list[dict[str, Any]]:
    return list((data.get("monitoring_thresholds") or {}).get("lgd_thresholds") or [])


def get_ead_model_options(data: dict) -> list[str]:
    portfolio: pl.DataFrame = data["portfolio"]
    if config.EAD_MODEL_COLUMN not in portfolio.columns:
        return []
    values = portfolio.select(config.EAD_MODEL_COLUMN).to_series().to_list()
    return sorted({text for value in values if (text := _clean_text(value))}, key=str.lower)


def get_ead_default_model(data: dict) -> str:
    return EAD_ALL_MODELS_LABEL


def resolve_ead_model(data: dict, selected_model: str | None) -> str:
    if selected_model in {EAD_ALL_MODELS_LABEL, "All", None, ""}:
        return EAD_ALL_MODELS_LABEL
    models = get_ead_model_options(data)
    if selected_model in models:
        return str(selected_model)
    return EAD_ALL_MODELS_LABEL


def get_ead_segments_for_model(data: dict, selected_model: str | None) -> list[str]:
    portfolio: pl.DataFrame = data["portfolio"]
    model = resolve_ead_model(data, selected_model)
    if config.SEGMENT_COLUMN not in portfolio.columns or config.EAD_MODEL_COLUMN not in portfolio.columns:
        return ["All"]

    df = portfolio.filter(pl.col(config.EAD_MODEL_COLUMN).cast(pl.String).str.strip_chars() != "")
    if model != EAD_ALL_MODELS_LABEL:
        df = df.filter(pl.col(config.EAD_MODEL_COLUMN).cast(pl.String) == model)
    values = df.select(config.SEGMENT_COLUMN).to_series().to_list()
    segments = sorted({text for value in values if (text := _clean_text(value))}, key=str.lower)
    return ["All", *segments]


def resolve_ead_segment(data: dict, selected_model: str | None, selected_segment: str | None) -> str:
    segments = get_ead_segments_for_model(data, selected_model)
    return selected_segment if selected_segment in segments else "All"


def filter_ead_portfolio(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> pl.DataFrame:
    portfolio: pl.DataFrame = data["portfolio"]
    model = resolve_ead_model(data, selected_model)
    if config.EAD_MODEL_COLUMN not in portfolio.columns:
        return portfolio.clear()

    df = portfolio.filter(pl.col(config.EAD_MODEL_COLUMN).cast(pl.String).str.strip_chars() != "")
    if model != EAD_ALL_MODELS_LABEL:
        df = df.filter(pl.col(config.EAD_MODEL_COLUMN).cast(pl.String) == model)
    segment = resolve_ead_segment(data, model, selected_segment)
    if segment != "All" and config.SEGMENT_COLUMN in df.columns:
        df = df.filter(pl.col(config.SEGMENT_COLUMN).cast(pl.String) == segment)
    return df


def build_ead_observations(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> pl.DataFrame:
    df = filter_ead_portfolio(data, selected_model, selected_segment)
    required = [config.EAD_PREDICTED_1Y_COLUMN, config.LIMIT_AMOUNT_COLUMN, "_quarter"]
    if df.is_empty() or any(column not in df.columns for column in required):
        return pl.DataFrame()

    raw_predicted = pl.col(config.EAD_PREDICTED_1Y_COLUMN).cast(pl.Float64, strict=False)
    limit = pl.col(config.LIMIT_AMOUNT_COLUMN).cast(pl.Float64, strict=False)
    if config.EAD_REALIZED_COLUMN in df.columns:
        raw_actual = pl.col(config.EAD_REALIZED_COLUMN).cast(pl.Float64, strict=False)
    elif config.PD_OBSERVED_DEFAULT_1Y_COLUMN in df.columns:
        raw_actual = pl.when(pl.col(config.PD_OBSERVED_DEFAULT_1Y_COLUMN).cast(pl.Float64, strict=False) == 1).then(raw_predicted).otherwise(0.0)
    else:
        raw_actual = raw_predicted

    valid_limit = limit.is_not_null() & (limit > 0)
    predicted = pl.when(valid_limit).then(raw_predicted / limit).otherwise(None)
    actual = pl.when(valid_limit).then(raw_actual / limit).otherwise(None)

    payload_columns = [
        column
        for column in [
            "_quarter",
            config.SEGMENT_COLUMN,
            config.EAD_MODEL_COLUMN,
            config.EAD_PREDICTED_1Y_COLUMN,
            config.LIMIT_AMOUNT_COLUMN,
            config.EAD_REALIZED_COLUMN,
            config.PD_OBSERVED_DEFAULT_1Y_COLUMN,
        ]
        if column in df.columns
    ]

    return (
        df.select(payload_columns)
        .with_columns(
            predicted.alias("predicted_ead"),
            actual.alias("actual_ead"),
            pl.col(config.PD_OBSERVED_DEFAULT_1Y_COLUMN).cast(pl.Float64, strict=False).alias("default_flag_1y")
            if config.PD_OBSERVED_DEFAULT_1Y_COLUMN in df.columns
            else pl.lit(None, dtype=pl.Float64).alias("default_flag_1y"),
        )
        .with_columns((pl.col("actual_ead") - pl.col("predicted_ead")).alias("ead_error"))
        .filter(
            pl.col("_quarter").is_not_null()
            & pl.col("predicted_ead").is_not_null()
            & pl.col("actual_ead").is_not_null()
        )
    )


def get_ead_periods(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    observations = build_ead_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []
    values = observations.select("_quarter").to_series().to_list()
    return sorted({str(value) for value in values if value}, key=_quarter_sort_key)


def get_ead_monitoring_point_options(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    periods = get_ead_periods(data, selected_model, selected_segment)
    return ["Latest", *reversed(periods)]


def resolve_ead_monitoring_point(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
) -> str:
    periods = get_ead_periods(data, selected_model, selected_segment)
    if not periods:
        return ""
    if selected_monitoring_point in periods:
        return str(selected_monitoring_point)
    return periods[-1]


def ead_metrics_by_period(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[dict[str, Any]]:
    observations = build_ead_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []

    rows: list[dict[str, Any]] = []
    for key, period_df in observations.partition_by("_quarter", as_dict=True).items():
        period = key[0] if isinstance(key, tuple) else key
        errors = period_df.get_column("ead_error").to_list()
        actual = period_df.get_column("actual_ead").to_list()
        predicted = period_df.get_column("predicted_ead").to_list()
        mean_error = _mean(errors)
        rmse = math.sqrt(_mean([error * error for error in errors]) or 0.0) if any(_is_finite(error) for error in errors) else None

        rows.append(
            {
                "Monitoring Period": str(period),
                "ME": mean_error,
                "RMSE": rmse,
                "Kendall's Tau": _kendall_tau(predicted, actual),
                "Predicted EAD": _mean(predicted),
                "Actual EAD": _mean(actual),
                "Observations": period_df.height,
                "Defaults": int(period_df.filter(pl.col("default_flag_1y") == 1).height),
            }
        )

    return sorted(rows, key=lambda row: _quarter_sort_key(row["Monitoring Period"]))


def ead_metric_rag(data: dict, metric: str, value: Any) -> str:
    return calculate_pd_metric_rag(get_ead_thresholds(data), metric, value)


def build_ead_period_summary(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None = "All",
    selected_monitoring_point: str | None = "Latest",
) -> dict[str, Any]:
    metric_rows = ead_metrics_by_period(data, selected_model, selected_segment)
    monitoring_point = resolve_ead_monitoring_point(data, selected_model, selected_segment, selected_monitoring_point)
    current_index = next((index for index, row in enumerate(metric_rows) if row["Monitoring Period"] == monitoring_point), -1)
    current = metric_rows[current_index] if current_index >= 0 else {}
    previous = metric_rows[current_index - 1] if current_index > 0 else {}

    metric_rags = {metric: ead_metric_rag(data, metric, current.get(metric)) for metric in EAD_METRICS}
    previous_metric_rags = {metric: ead_metric_rag(data, metric, previous.get(metric)) for metric in EAD_METRICS}
    calibration_rag = get_worst_pd_rag([metric_rags[metric] for metric in EAD_CALIBRATION_METRICS])
    previous_calibration_rag = get_worst_pd_rag([previous_metric_rags[metric] for metric in EAD_CALIBRATION_METRICS])
    discrimination_rag = get_worst_pd_rag([metric_rags[metric] for metric in EAD_DISCRIMINATION_METRICS])
    previous_discrimination_rag = get_worst_pd_rag([previous_metric_rags[metric] for metric in EAD_DISCRIMINATION_METRICS])
    performance_rag = get_worst_pd_rag([calibration_rag, discrimination_rag])
    previous_performance_rag = get_worst_pd_rag([previous_calibration_rag, previous_discrimination_rag])

    return {
        "metric_rows": metric_rows,
        "current": current,
        "previous": previous,
        "monitoring_point": monitoring_point,
        "previous_monitoring_point": previous.get("Monitoring Period", ""),
        "metric_rags": metric_rags,
        "previous_metric_rags": previous_metric_rags,
        "calibration_rag": calibration_rag,
        "previous_calibration_rag": previous_calibration_rag,
        "discrimination_rag": discrimination_rag,
        "previous_discrimination_rag": previous_discrimination_rag,
        "performance_rag": performance_rag,
        "previous_performance_rag": previous_performance_rag,
    }


def build_ead_calibration_rag_trend(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        me_rag = ead_metric_rag(data, "ME", row.get("ME"))
        rmse_rag = ead_metric_rag(data, "RMSE", row.get("RMSE"))
        rag = get_worst_pd_rag([me_rag, rmse_rag])
        scores = [pd_rag_score(metric_rag) for metric_rag in (me_rag, rmse_rag)]
        scores = [score for score in scores if score is not None]
        weighted_average = sum(scores) / len(scores) if scores else None
        rounded_score = round(weighted_average) if weighted_average is not None else None
        rows.append(
            {
                "quarter": row["Monitoring Period"],
                "rag": rag,
                "rag_score": pd_rag_score(rag),
                "weighted_average": weighted_average,
                "rounded_score": rounded_score,
                "me": row.get("ME"),
                "me_rag": me_rag,
                "rmse": row.get("RMSE"),
                "rmse_rag": rmse_rag,
            }
        )
    return rows


def build_ead_discrimination_rag_trend(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        tau_rag = ead_metric_rag(data, "Kendall's Tau", row.get("Kendall's Tau"))
        score = pd_rag_score(tau_rag)
        rows.append(
            {
                "quarter": row["Monitoring Period"],
                "rag": tau_rag,
                "rag_score": score,
                "weighted_average": score,
                "rounded_score": score,
                "kendall_tau": row.get("Kendall's Tau"),
                "kendall_tau_rag": tau_rag,
            }
        )
    return rows
