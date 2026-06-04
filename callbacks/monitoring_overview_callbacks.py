"""Monitoring overview callbacks — build the data payload for the monitoring overview page."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from callbacks.monitoring_pd_models_callbacks import build_pd_overview_status_rows


log = logging.getLogger(__name__)


def _normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _latest_snapshot(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if df.empty or date_column not in df.columns:
        return df.copy()
    latest_date = df[date_column].max()
    return df[df[date_column] == latest_date].copy()


def _build_lgd_ead_overview_rows(df: pd.DataFrame, cfg: dict) -> list[dict[str, str]]:
    data_cfg = cfg.get("data", {})
    segment_column = data_cfg.get("segment_column", "segment")
    date_column = data_cfg.get("date_column", "MONTH END-SNAPSHOT DATE")
    definitions = [
        ("LGD", "lgd", data_cfg.get("lgd_model_column", "lgd_model")),
        ("EAD", "ead", data_cfg.get("ead_model_column", "ead_model")),
    ]
    rows = []

    for model_group, config_prefix, model_column in definitions:
        for horizon in ("1y", "2y"):
            predicted_column = data_cfg.get(
                f"{config_prefix}_predicted_{horizon}_column",
                data_cfg.get(
                    f"{config_prefix}_predicted_{horizon}_base_column",
                    data_cfg.get(f"{config_prefix}_predicted_column", f"{model_group}_{horizon}_base"),
                ),
            )
            required = ["_quarter", model_column, segment_column, date_column, predicted_column]
            missing = [column for column in required if column not in df.columns]
            if missing:
                log.warning("%s %s overview columns not found: %s", model_group, horizon, missing)
                continue

            normalized = df[required].copy()
            normalized[model_column] = normalized[model_column].map(_normalize_text)
            normalized[segment_column] = normalized[segment_column].map(_normalize_text)
            normalized[predicted_column] = pd.to_numeric(normalized[predicted_column], errors="coerce")
            normalized = normalized[
                (normalized[model_column] != "")
                & (normalized[segment_column] != "")
                & normalized[predicted_column].notna()
            ]

            for (quarter, model, segment), group in normalized.groupby(["_quarter", model_column, segment_column]):
                latest = _latest_snapshot(group, date_column)
                average_output = latest[predicted_column].mean()
                if model_group == "LGD":
                    overall_rag = "Green" if average_output <= 0.45 else "Amber" if average_output <= 0.60 else "Red"
                else:
                    overall_rag = "Green" if average_output <= latest[predicted_column].quantile(0.75) else "Amber"
                rows.append(
                    {
                        "monitoring_period": quarter,
                        "time_horizon": horizon,
                        "model": model,
                        "model_group": model_group,
                        "segment": segment,
                        "overall_rag": overall_rag,
                        "pre_mitigation_rag": overall_rag,
                        "post_mitigation_rag": overall_rag,
                    }
                )
    return rows


def _build_model_status_rows(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> list[dict[str, str]]:
    rows = build_pd_overview_status_rows(df, thresholds, cfg)
    rows.extend(_build_lgd_ead_overview_rows(df, cfg))
    return rows


def build_monitoring_overview(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> dict[str, Any]:
    id_col = cfg.get("population", {}).get("id_column", "facility id")
    total_accounts = int(df[id_col].nunique()) if id_col in df.columns else len(df)
    total_records = len(df)
    quarters = sorted(set(df["_quarter"])) if "_quarter" in df.columns else []
    latest_quarter = quarters[-1] if quarters else ""

    sheet_name_map = {
        key[: -len("_sheet_name")]: val
        for key, val in cfg["data"].items()
        if key.endswith("_thresholds_sheet_name") and isinstance(val, str)
    }

    sheet_summary = []
    total_threshold_rows = 0
    empty_threshold_sheets = 0

    for key, sheet_name in sheet_name_map.items():
        df_sheet = thresholds.get(key, pd.DataFrame())
        rows = len(df_sheet) if isinstance(df_sheet, pd.DataFrame) else 0
        cols = len(df_sheet.columns) if isinstance(df_sheet, pd.DataFrame) else 0
        is_empty = rows == 0
        if is_empty:
            empty_threshold_sheets += 1
        total_threshold_rows += rows
        sheet_summary.append({
            "sheet_key": key,
            "sheet_name": sheet_name,
            "rows": rows,
            "cols": cols,
            "is_empty": is_empty,
        })

    sheet_summary.sort(key=lambda row: row["sheet_name"])
    model_status_rows = _build_model_status_rows(df, thresholds, cfg)
    model_names = sorted({row["model"] for row in model_status_rows})
    segment_values = sorted({row["segment"] for row in model_status_rows})

    return {
        "portfolio_records": total_records,
        "unique_accounts": total_accounts,
        "latest_quarter": latest_quarter,
        "thresholds_file": cfg["data"].get("monitoring_thresholds_file", ""),
        "threshold_sheet_count": len(sheet_summary),
        "total_threshold_rows": total_threshold_rows,
        "empty_threshold_sheets": empty_threshold_sheets,
        "sheet_summary": sheet_summary,
        "model_status_rows": model_status_rows,
        "model_names": model_names,
        "segment_values": segment_values,
        "overview_text": (
            "This page summarizes model status for the selected monitoring point. "
            "Where a model spans segments or available horizons, its worst RAG status is retained."
        ),
    }
