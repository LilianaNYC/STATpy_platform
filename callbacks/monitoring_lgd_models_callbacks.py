"""Callbacks for the model monitoring dashboard LGD Performance tab."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _build_lgd_performance_observations(
    df: pd.DataFrame,
    model_column: str,
    segment_column: str,
    cfg: dict,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the compact row-level payload needed for interactive LGD metrics."""
    data_cfg = cfg.get("data", {})
    rating_column = data_cfg.get("rating_column", "rating_grade")
    realized_column = data_cfg.get("lgd_realized_column", "realized_lgd")
    horizon_columns = {
        "1y": {
            "label": "1 year",
            "predicted_column": data_cfg.get(
                "lgd_predicted_1y_column",
                data_cfg.get("lgd_predicted_1y_base_column", "LGD_1y_base"),
            ),
        },
        "2y": {
            "label": "2 years",
            "predicted_column": data_cfg.get(
                "lgd_predicted_2y_column",
                data_cfg.get("lgd_predicted_2y_base_column", "LGD_2y_base"),
            ),
        },
    }
    required = [model_column, segment_column, "_quarter", realized_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        log.warning("LGD performance columns not found: %s", missing)
        return horizon_columns, []

    available_horizons = {}
    for horizon, columns in horizon_columns.items():
        predicted_column = columns["predicted_column"]
        if predicted_column not in df.columns:
            log.warning("LGD %s performance column not found: %s", horizon, predicted_column)
            continue
        available_horizons[horizon] = columns

    payload_columns = list(dict.fromkeys(required + (
        [rating_column] if rating_column in df.columns else []
    ) + [
        columns["predicted_column"]
        for columns in available_horizons.values()
    ]))
    observations = df[payload_columns].copy()
    observations[model_column] = observations[model_column].map(_normalize_text)
    observations[segment_column] = observations[segment_column].map(_normalize_text)
    observations[realized_column] = pd.to_numeric(observations[realized_column], errors="coerce")
    observations = observations.dropna(subset=["_quarter", realized_column])
    observations = observations[
        (observations[model_column] != "")
        & (observations[segment_column] != "")
        & observations[realized_column].between(0, 1)
    ]

    for columns in available_horizons.values():
        predicted_column = columns["predicted_column"]
        observations[predicted_column] = pd.to_numeric(observations[predicted_column], errors="coerce")

    result = []
    for _, row in observations.iterrows():
        horizons = {}
        for horizon, columns in available_horizons.items():
            predicted = row[columns["predicted_column"]]
            if not pd.isna(predicted) and 0 <= predicted <= 1:
                horizons[horizon] = {"predicted": round(float(predicted), 8)}
        if horizons:
            result.append(
                {
                    "quarter": str(row["_quarter"]),
                    "model": row[model_column],
                    "segment": row[segment_column],
                    "rating": _normalize_text(row[rating_column]) if rating_column in observations.columns else "",
                    "realized": round(float(row[realized_column]), 8),
                    "horizons": horizons,
                }
            )

    return horizon_columns, result


def build_monitoring_lgd_models(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> dict[str, Any]:
    """Build the payload consumed by the LGD Performance tab."""
    data_cfg = cfg.get("data", {})
    model_column = data_cfg.get("lgd_model_column", "lgd_model")
    segment_column = data_cfg.get("segment_column", "segment")
    id_column = cfg.get("population", {}).get("id_column", data_cfg.get("facility_id_column", "facility id"))

    models = []
    if model_column in df.columns:
        models = sorted(value for value in df[model_column].map(_normalize_text).unique() if value)

    segments = []
    if segment_column in df.columns:
        segments = sorted(value for value in df[segment_column].map(_normalize_text).unique() if value)

    horizons, observations = _build_lgd_performance_observations(df, model_column, segment_column, cfg)
    return {
        "model_column": model_column,
        "model_names": models,
        "segment_column": segment_column,
        "segment_values": segments,
        "portfolio_records": len(df),
        "portfolio_unique_accounts": int(df[id_column].nunique()) if id_column in df.columns else len(df),
        "performance_horizons": horizons,
        "performance_observations": observations,
    }
