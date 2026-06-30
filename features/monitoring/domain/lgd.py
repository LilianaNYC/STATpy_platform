"""LGD performance data preparation.

Calculates ME, RMSE, and Kendall's Tau by monitoring period using the
portfolio's LGD columns and LGD threshold workbook sheet.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from ....shared.domain import constants as config
from ....shared.domain.calculations import calculate_pd_metric_rag, get_worst_pd_rag, pd_rag_score

LGD_METRICS = ["ME", "RMSE", "Kendall's Tau"]
LGD_CALIBRATION_METRICS = ["ME", "RMSE"]
LGD_DISCRIMINATION_METRICS = ["Kendall's Tau"]
LGD_ALL_MODELS_LABEL = "All models"


# ---------------------------------------------------------------------------
# Precomputed-metrics store
# ---------------------------------------------------------------------------
# The LGD tab reads metric rows straight from ``LGD_Performance_Metrics`` via a
# store keyed by ``(level, value)`` (``level`` = ``model``/``segment``;
# ``value`` = the model name, ``"All Models"``, or a segment name). The cycle
# callback installs the selected reporting cycle's store and quarters here.

_LGD_STORE: dict | None = None
_LGD_QUARTERS: list[str] = []


def set_lgd_metrics(store: dict | None, quarters: list[str] | None = None) -> None:
    """Install (or clear) the precomputed LGD metrics store and its quarters."""
    global _LGD_STORE, _LGD_QUARTERS
    _LGD_STORE = store
    _LGD_QUARTERS = list(quarters or [])


def _lgd_store_key(selected_model, selected_segment) -> tuple[str, str]:
    """Map a (model, segment) selection to a ``(level, value)`` store key.

    The model and segment filters are mutually exclusive, so the selection
    collapses to a single entity: a segment, a single model, or all models.
    """
    segment = selected_segment if isinstance(selected_segment, str) else None
    if segment and segment not in ("All", "all", ""):
        return "segment", segment
    if isinstance(selected_model, (list, tuple, set)):
        models = [m for m in selected_model if m]
        model = models[0] if len(models) == 1 else None
    else:
        model = selected_model
    if model and model not in ("all", "All", LGD_ALL_MODELS_LABEL, ""):
        return "model", str(model)
    return "model", "All Models"


def _lgd_store_rows(selected_model, selected_segment) -> list[dict] | None:
    if _LGD_STORE is None:
        return None
    return _LGD_STORE.get(_lgd_store_key(selected_model, selected_segment), [])


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


def get_lgd_thresholds(data: dict) -> list[dict[str, Any]]:
    return list((data.get("monitoring_thresholds") or {}).get("lgd_thresholds") or [])


def get_lgd_model_options(data: dict) -> list[str]:
    from ....shared.repositories.filters_config import model_names
    options = model_names("lgd")
    if options:
        return options
    portfolio: pl.DataFrame = data.get("portfolio")
    if portfolio is None or config.LGD_MODEL_COLUMN not in portfolio.columns:
        return []
    values = portfolio.select(config.LGD_MODEL_COLUMN).to_series().to_list()
    return sorted({text for value in values if (text := _clean_text(value))}, key=str.lower)


def get_lgd_default_model(data: dict) -> str:
    return LGD_ALL_MODELS_LABEL


def resolve_lgd_models(data: dict, selected_model: str | list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    models = get_lgd_model_options(data)
    if isinstance(selected_model, (list, tuple, set)):
        selected = [str(value) for value in selected_model if value in models]
        return selected
    if selected_model in {LGD_ALL_MODELS_LABEL, "All", None, ""}:
        return []
    if selected_model in models:
        return [str(selected_model)]
    return []



def get_lgd_segments_for_model(data: dict, selected_model: str | list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    from ....shared.repositories.filters_config import segment_values
    segments = segment_values()
    if segments:
        return ["All", *segments]
    portfolio: pl.DataFrame = data.get("portfolio")
    if portfolio is None or config.SEGMENT_COLUMN not in portfolio.columns or config.LGD_MODEL_COLUMN not in portfolio.columns:
        return ["All"]
    df = portfolio.filter(pl.col(config.LGD_MODEL_COLUMN).cast(pl.String).str.strip_chars() != "")
    values = df.select(config.SEGMENT_COLUMN).to_series().to_list()
    segments = sorted({text for value in values if (text := _clean_text(value))}, key=str.lower)
    return ["All", *segments]


def resolve_lgd_segment(
    data: dict,
    selected_model: str | list[str] | tuple[str, ...] | set[str] | None,
    selected_segment: str | None,
) -> str:
    segments = get_lgd_segments_for_model(data, selected_model)
    return selected_segment if selected_segment in segments else "All"


def filter_lgd_portfolio(
    data: dict,
    selected_model: str | list[str] | tuple[str, ...] | set[str] | None,
    selected_segment: str | None = "All",
) -> pl.DataFrame:
    portfolio: pl.DataFrame = data["portfolio"]
    selected_models = resolve_lgd_models(data, selected_model)
    if config.LGD_MODEL_COLUMN not in portfolio.columns:
        return portfolio.clear()

    df = portfolio.filter(pl.col(config.LGD_MODEL_COLUMN).cast(pl.String).str.strip_chars() != "")
    if selected_models:
        df = df.filter(pl.col(config.LGD_MODEL_COLUMN).cast(pl.String).is_in(selected_models))
    segment = resolve_lgd_segment(data, selected_models, selected_segment)
    if segment != "All" and config.SEGMENT_COLUMN in df.columns:
        df = df.filter(pl.col(config.SEGMENT_COLUMN).cast(pl.String) == segment)
    return df


def build_lgd_observations(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> pl.DataFrame:
    df = filter_lgd_portfolio(data, selected_model, selected_segment)
    required = [config.LGD_PREDICTED_1Y_COLUMN, "_quarter"]
    if df.is_empty() or any(column not in df.columns for column in required):
        return pl.DataFrame()

    predicted = pl.col(config.LGD_PREDICTED_1Y_COLUMN).cast(pl.Float64, strict=False)
    if config.LGD_REALIZED_COLUMN in df.columns:
        actual = pl.col(config.LGD_REALIZED_COLUMN).cast(pl.Float64, strict=False)
    elif config.PD_OBSERVED_DEFAULT_1Y_COLUMN in df.columns:
        actual = pl.when(pl.col(config.PD_OBSERVED_DEFAULT_1Y_COLUMN).cast(pl.Float64, strict=False) == 1).then(predicted).otherwise(0.0)
    else:
        actual = predicted

    payload_columns = [column for column in [
        "_quarter",
        config.SEGMENT_COLUMN,
        config.LGD_MODEL_COLUMN,
        config.LGD_PREDICTED_1Y_COLUMN,
        config.LGD_REALIZED_COLUMN,
        config.PD_OBSERVED_DEFAULT_1Y_COLUMN,
    ] if column in df.columns]

    return (
        df.select(payload_columns)
        .with_columns(
            predicted.alias("predicted_lgd"),
            actual.alias("actual_lgd"),
            pl.col(config.PD_OBSERVED_DEFAULT_1Y_COLUMN).cast(pl.Float64, strict=False).alias("default_flag_1y")
            if config.PD_OBSERVED_DEFAULT_1Y_COLUMN in df.columns
            else pl.lit(None, dtype=pl.Float64).alias("default_flag_1y"),
        )
        .with_columns((pl.col("actual_lgd") - pl.col("predicted_lgd")).alias("lgd_error"))
        .filter(
            pl.col("_quarter").is_not_null()
            & pl.col("predicted_lgd").is_not_null()
            & pl.col("actual_lgd").is_not_null()
        )
    )


def get_lgd_periods(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    rows = _lgd_store_rows(selected_model, selected_segment)
    if rows is not None:
        return sorted({str(r["Monitoring Period"]) for r in rows if r.get("Monitoring Period")}, key=_quarter_sort_key)
    observations = build_lgd_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []
    values = observations.select("_quarter").to_series().to_list()
    return sorted({str(value) for value in values if value}, key=_quarter_sort_key)


def get_lgd_monitoring_point_options(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    periods = get_lgd_periods(data, selected_model, selected_segment)
    return ["Latest", *reversed(periods)]


def resolve_lgd_monitoring_point(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
) -> str:
    periods = get_lgd_periods(data, selected_model, selected_segment)
    if not periods:
        return ""
    if selected_monitoring_point in periods:
        return str(selected_monitoring_point)
    return periods[-1]


def lgd_metrics_by_period(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[dict[str, Any]]:
    rows = _lgd_store_rows(selected_model, selected_segment)
    if rows is not None:
        return sorted((dict(r) for r in rows), key=lambda r: _quarter_sort_key(r["Monitoring Period"]))

    observations = build_lgd_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []

    rows: list[dict[str, Any]] = []
    for key, period_df in observations.partition_by("_quarter", as_dict=True).items():
        period = key[0] if isinstance(key, tuple) else key
        errors = period_df.get_column("lgd_error").to_list()
        actual = period_df.get_column("actual_lgd").to_list()
        predicted = period_df.get_column("predicted_lgd").to_list()
        mean_error = _mean(errors)
        rmse = math.sqrt(_mean([error * error for error in errors]) or 0.0) if any(_is_finite(error) for error in errors) else None
        predicted_lgd = _mean(predicted)
        actual_lgd = _mean(actual)
        recovery_rate = 1 - actual_lgd if _is_finite(actual_lgd) else None

        rows.append(
            {
                "Monitoring Period": str(period),
                "ME": mean_error,
                "RMSE": rmse,
                "Kendall's Tau": _kendall_tau(predicted, actual),
                "Predicted LGD": predicted_lgd,
                "Actual LGD": actual_lgd,
                "Recovery Rate": recovery_rate,
                "Observations": period_df.height,
                "Defaults": int(period_df.filter(pl.col("default_flag_1y") == 1).height),
            }
        )

    return sorted(rows, key=lambda row: _quarter_sort_key(row["Monitoring Period"]))


def lgd_metric_rag(data: dict, metric: str, value: Any) -> str:
    return calculate_pd_metric_rag(get_lgd_thresholds(data), metric, value)


def build_lgd_period_summary(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None = "All",
    selected_monitoring_point: str | None = "Latest",
) -> dict[str, Any]:
    metric_rows = lgd_metrics_by_period(data, selected_model, selected_segment)
    monitoring_point = resolve_lgd_monitoring_point(data, selected_model, selected_segment, selected_monitoring_point)
    current_index = next((index for index, row in enumerate(metric_rows) if row["Monitoring Period"] == monitoring_point), -1)
    current = metric_rows[current_index] if current_index >= 0 else {}
    previous = metric_rows[current_index - 1] if current_index > 0 else {}

    metric_rags = {metric: lgd_metric_rag(data, metric, current.get(metric)) for metric in LGD_METRICS}
    previous_metric_rags = {metric: lgd_metric_rag(data, metric, previous.get(metric)) for metric in LGD_METRICS}
    calibration_rag = get_worst_pd_rag([metric_rags[metric] for metric in LGD_CALIBRATION_METRICS])
    previous_calibration_rag = get_worst_pd_rag([previous_metric_rags[metric] for metric in LGD_CALIBRATION_METRICS])
    discrimination_rag = get_worst_pd_rag([metric_rags[metric] for metric in LGD_DISCRIMINATION_METRICS])
    previous_discrimination_rag = get_worst_pd_rag([previous_metric_rags[metric] for metric in LGD_DISCRIMINATION_METRICS])
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


def build_lgd_heatmap_rows(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Metric": metric,
            **{
                row["Monitoring Period"]: lgd_metric_rag(data, metric, row.get(metric))
                for row in metric_rows
            },
        }
        for metric in LGD_METRICS
    ]


def build_lgd_calibration_rag_trend(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        me_rag = lgd_metric_rag(data, "ME", row.get("ME"))
        rmse_rag = lgd_metric_rag(data, "RMSE", row.get("RMSE"))
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


def build_lgd_discrimination_rag_trend(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        tau_rag = lgd_metric_rag(data, "Kendall's Tau", row.get("Kendall's Tau"))
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
