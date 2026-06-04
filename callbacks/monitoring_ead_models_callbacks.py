"""Callbacks for the model monitoring dashboard EAD Performance tab."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _build_ead_performance_observations(
    df: pd.DataFrame,
    model_column: str,
    segment_column: str,
    cfg: dict,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the compact row-level payload needed for interactive EAD metrics."""
    data_cfg = cfg.get("data", {})
    rating_column = data_cfg.get("rating_column", "rating_grade")
    observed_column = data_cfg.get("ead_observed_column", "Balance")
    limit_column = data_cfg.get("ead_limit_column", "limit_amount")
    undrawn_column = data_cfg.get("ead_undrawn_column", "undrawn_amount")
    horizon_columns = {
        "1y": {
            "label": "1 year",
            "predicted_column": data_cfg.get(
                "ead_predicted_1y_column",
                data_cfg.get("ead_predicted_1y_base_column", "EAD_1y_base"),
            ),
        },
        "2y": {
            "label": "2 years",
            "predicted_column": data_cfg.get(
                "ead_predicted_2y_column",
                data_cfg.get("ead_predicted_2y_base_column", "EAD_2y_base"),
            ),
        },
    }
    required = [model_column, segment_column, "_quarter", observed_column, limit_column, undrawn_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        log.warning("EAD performance columns not found: %s", missing)
        return horizon_columns, []

    available_horizons = {}
    for horizon, columns in horizon_columns.items():
        predicted_column = columns["predicted_column"]
        if predicted_column not in df.columns:
            log.warning("EAD %s performance column not found: %s", horizon, predicted_column)
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
    observations[observed_column] = pd.to_numeric(observations[observed_column], errors="coerce")
    observations[limit_column] = pd.to_numeric(observations[limit_column], errors="coerce")
    observations[undrawn_column] = pd.to_numeric(observations[undrawn_column], errors="coerce")
    observations = observations.dropna(subset=["_quarter", observed_column, limit_column, undrawn_column])
    observations = observations[
        (observations[model_column] != "")
        & (observations[segment_column] != "")
        & (observations[observed_column] >= 0)
        & (observations[limit_column] > 0)
        & (observations[undrawn_column] >= 0)
    ]

    for columns in available_horizons.values():
        predicted_column = columns["predicted_column"]
        observations[predicted_column] = pd.to_numeric(observations[predicted_column], errors="coerce")

    result = []
    for _, row in observations.iterrows():
        horizons = {}
        for horizon, columns in available_horizons.items():
            predicted = row[columns["predicted_column"]]
            if not pd.isna(predicted) and predicted >= 0:
                horizons[horizon] = {"predicted": round(float(predicted), 8)}
        if horizons:
            result.append(
                {
                    "quarter": str(row["_quarter"]),
                    "model": row[model_column],
                    "segment": row[segment_column],
                    "rating": _normalize_text(row[rating_column]) if rating_column in observations.columns else "",
                    "observed": round(float(row[observed_column]), 8),
                    "limit": round(float(row[limit_column]), 8),
                    "undrawn": round(float(row[undrawn_column]), 8),
                    "horizons": horizons,
                }
            )

    return horizon_columns, result


def build_monitoring_ead_models(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> dict[str, Any]:
    """Build the payload consumed by the EAD Performance tab."""
    data_cfg = cfg.get("data", {})
    model_column = data_cfg.get("ead_model_column", "ead_model")
    segment_column = data_cfg.get("segment_column", "segment")
    id_column = cfg.get("population", {}).get("id_column", data_cfg.get("facility_id_column", "facility id"))

    models = []
    if model_column in df.columns:
        models = sorted(value for value in df[model_column].map(_normalize_text).unique() if value)

    segments = []
    if segment_column in df.columns:
        segments = sorted(value for value in df[segment_column].map(_normalize_text).unique() if value)

    horizons, observations = _build_ead_performance_observations(df, model_column, segment_column, cfg)
    return {
        "model_column": model_column,
        "model_names": models,
        "segment_column": segment_column,
        "segment_values": segments,
        "portfolio_records": len(df),
        "portfolio_unique_accounts": int(df[id_column].nunique()) if id_column in df.columns else len(df),
        "observation_basis": f"{data_cfg.get('ead_observed_column', 'Balance')} (current drawn exposure proxy)",
        "performance_horizons": horizons,
        "performance_observations": observations,
    }
