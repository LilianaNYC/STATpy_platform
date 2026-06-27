"""Loss performance data preparation."""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from ....data.analytics import constants as config
from ....data.analytics.calculations import calculate_pd_metric_rag, pd_rag_score

LOSS_METRICS = ["ME %"]
LOSS_MODEL_LABEL = "Loss model"


# ---------------------------------------------------------------------------
# Precomputed-metrics store
# ---------------------------------------------------------------------------
# The Loss tab reads metric rows straight from ``Loss_Performance_Metrics`` via
# a store keyed by ``(level, value)``. There is a single loss model, so the
# model-level entity is ``"Loss model"``. The cycle callback installs the
# selected reporting cycle's store and quarters here.

_LOSS_STORE: dict | None = None
_LOSS_QUARTERS: list[str] = []


def set_loss_metrics(store: dict | None, quarters: list[str] | None = None) -> None:
    """Install (or clear) the precomputed Loss metrics store and its quarters."""
    global _LOSS_STORE, _LOSS_QUARTERS
    _LOSS_STORE = store
    _LOSS_QUARTERS = list(quarters or [])


def _loss_store_key(selected_model, selected_segment) -> tuple[str, str]:
    """Map a (model, segment) selection to a ``(level, value)`` store key."""
    segment = selected_segment if isinstance(selected_segment, str) else None
    if segment and segment not in ("All", "all", ""):
        return "segment", segment
    return "model", LOSS_MODEL_LABEL


def _loss_store_rows(selected_model, selected_segment) -> list[dict] | None:
    if _LOSS_STORE is None:
        return None
    return _LOSS_STORE.get(_loss_store_key(selected_model, selected_segment), [])


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


def get_loss_thresholds(data: dict) -> list[dict[str, Any]]:
    return list((data.get("monitoring_thresholds") or {}).get("loss_thresholds") or [])


def get_loss_model_options(data: dict) -> list[str]:
    return [LOSS_MODEL_LABEL]


def get_loss_default_model(data: dict) -> str:
    return LOSS_MODEL_LABEL


def resolve_loss_model(data: dict, selected_model: str | None) -> str:
    return LOSS_MODEL_LABEL


def get_loss_segments_for_model(data: dict, selected_model: str | None) -> list[str]:
    from ....data.monitoring.filters_config import segment_values
    segments = segment_values()
    if segments:
        return ["All", *segments]
    portfolio: pl.DataFrame = data.get("portfolio")
    if portfolio is None or config.SEGMENT_COLUMN not in portfolio.columns:
        return ["All"]
    values = portfolio.select(config.SEGMENT_COLUMN).to_series().to_list()
    segments = sorted({text for value in values if (text := _clean_text(value))}, key=str.lower)
    return ["All", *segments]


def resolve_loss_segment(data: dict, selected_model: str | None, selected_segment: str | None) -> str:
    segments = get_loss_segments_for_model(data, selected_model)
    return selected_segment if selected_segment in segments else "All"


def filter_loss_portfolio(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> pl.DataFrame:
    portfolio: pl.DataFrame = data["portfolio"]
    model = resolve_loss_model(data, selected_model)

    df = portfolio
    segment = resolve_loss_segment(data, model, selected_segment)
    if segment != "All" and config.SEGMENT_COLUMN in df.columns:
        df = df.filter(pl.col(config.SEGMENT_COLUMN).cast(pl.String) == segment)
    return df


def build_loss_observations(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> pl.DataFrame:
    df = filter_loss_portfolio(data, selected_model, selected_segment)
    required = [
        "_quarter",
        config.PD_PREDICTED_1Y_COLUMN,
        config.LGD_PREDICTED_1Y_COLUMN,
        config.EAD_PREDICTED_1Y_COLUMN,
        config.PD_OBSERVED_DEFAULT_1Y_COLUMN,
        config.BALANCE_COLUMN,
    ]
    if df.is_empty() or any(column not in df.columns for column in required):
        return pl.DataFrame()

    cpd = pl.col(config.PD_PREDICTED_1Y_COLUMN).cast(pl.Float64, strict=False)
    lgd = pl.col(config.LGD_PREDICTED_1Y_COLUMN).cast(pl.Float64, strict=False)
    ead = pl.col(config.EAD_PREDICTED_1Y_COLUMN).cast(pl.Float64, strict=False)
    default_flag = pl.col(config.PD_OBSERVED_DEFAULT_1Y_COLUMN).cast(pl.Float64, strict=False)
    balance = pl.col(config.BALANCE_COLUMN).cast(pl.Float64, strict=False)

    payload_columns = [
        column
        for column in [
            "_quarter",
            config.SEGMENT_COLUMN,
            config.FACILITY_ID_COLUMN,
            config.PD_MODEL_COLUMN,
            config.LGD_MODEL_COLUMN,
            config.EAD_MODEL_COLUMN,
            config.PD_PREDICTED_1Y_COLUMN,
            config.LGD_PREDICTED_1Y_COLUMN,
            config.EAD_PREDICTED_1Y_COLUMN,
            config.PD_OBSERVED_DEFAULT_1Y_COLUMN,
            config.BALANCE_COLUMN,
        ]
        if column in df.columns
    ]

    return (
        df.select(payload_columns)
        .with_columns(
            (cpd * lgd * ead).alias("predicted_loss"),
            (default_flag * lgd * balance).alias("actual_loss"),
            default_flag.alias("default_flag_1y"),
            balance.alias("balance_amount"),
        )
        .with_columns((pl.col("actual_loss") - pl.col("predicted_loss")).alias("loss_error"))
        .filter(
            pl.col("_quarter").is_not_null()
            & pl.col("predicted_loss").is_not_null()
            & pl.col("actual_loss").is_not_null()
        )
    )


def get_loss_periods(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    rows = _loss_store_rows(selected_model, selected_segment)
    if rows is not None:
        return sorted({str(r["Monitoring Period"]) for r in rows if r.get("Monitoring Period")}, key=_quarter_sort_key)
    observations = build_loss_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []
    values = observations.select("_quarter").to_series().to_list()
    return sorted({str(value) for value in values if value}, key=_quarter_sort_key)


def get_loss_monitoring_point_options(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[str]:
    periods = get_loss_periods(data, selected_model, selected_segment)
    return ["Latest", *reversed(periods)]


def resolve_loss_monitoring_point(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None,
    selected_monitoring_point: str | None,
) -> str:
    periods = get_loss_periods(data, selected_model, selected_segment)
    if not periods:
        return ""
    if selected_monitoring_point in periods:
        return str(selected_monitoring_point)
    return periods[-1]


def loss_metrics_by_period(data: dict, selected_model: str | None, selected_segment: str | None = "All") -> list[dict[str, Any]]:
    rows = _loss_store_rows(selected_model, selected_segment)
    if rows is not None:
        return sorted((dict(r) for r in rows), key=lambda r: _quarter_sort_key(r["Monitoring Period"]))

    observations = build_loss_observations(data, selected_model, selected_segment)
    if observations.is_empty():
        return []

    rows: list[dict[str, Any]] = []
    for key, period_df in observations.partition_by("_quarter", as_dict=True).items():
        period = key[0] if isinstance(key, tuple) else key
        predicted_loss = period_df.get_column("predicted_loss").sum()
        actual_loss = period_df.get_column("actual_loss").sum()
        mean_error = _mean(period_df.get_column("loss_error").to_list())
        me_pct = (mean_error / predicted_loss) if predicted_loss and _is_finite(predicted_loss) and _is_finite(mean_error) else None

        rows.append(
            {
                "Monitoring Period": str(period),
                "ME": mean_error,
                "ME %": me_pct,
                "Predicted Loss": predicted_loss,
                "Actual Loss": actual_loss,
                "Defaults": int(period_df.get_column("default_flag_1y").sum() or 0),
                "Balance": period_df.get_column("balance_amount").sum(),
                "Observations": period_df.height,
            }
        )

    return sorted(rows, key=lambda row: _quarter_sort_key(row["Monitoring Period"]))


def loss_metric_rag(data: dict, metric: str, value: Any) -> str:
    return calculate_pd_metric_rag(get_loss_thresholds(data), metric, value)


def build_loss_period_summary(
    data: dict,
    selected_model: str | None,
    selected_segment: str | None = "All",
    selected_monitoring_point: str | None = "Latest",
) -> dict[str, Any]:
    metric_rows = loss_metrics_by_period(data, selected_model, selected_segment)
    monitoring_point = resolve_loss_monitoring_point(data, selected_model, selected_segment, selected_monitoring_point)
    current_index = next((index for index, row in enumerate(metric_rows) if row["Monitoring Period"] == monitoring_point), -1)
    current = metric_rows[current_index] if current_index >= 0 else {}
    previous = metric_rows[current_index - 1] if current_index > 0 else {}

    performance_rag = loss_metric_rag(data, "ME %", current.get("ME %"))
    previous_performance_rag = loss_metric_rag(data, "ME %", previous.get("ME %"))

    return {
        "metric_rows": metric_rows,
        "current": current,
        "previous": previous,
        "monitoring_point": monitoring_point,
        "previous_monitoring_point": previous.get("Monitoring Period", ""),
        "metric_rags": {"ME %": performance_rag},
        "previous_metric_rags": {"ME %": previous_performance_rag},
        "performance_rag": performance_rag,
        "previous_performance_rag": previous_performance_rag,
    }


def build_loss_rag_trend(data: dict, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        rag = loss_metric_rag(data, "ME %", row.get("ME %"))
        score = pd_rag_score(rag)
        rows.append(
            {
                "quarter": row["Monitoring Period"],
                "rag": rag,
                "rag_score": score,
                "weighted_average": score,
                "rounded_score": score,
                "me": row.get("ME"),
                "me_pct": row.get("ME %"),
                "me_pct_rag": rag,
            }
        )
    return rows
