"""Callbacks for the model monitoring dashboard PD Performance tab."""

from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import roc_auc_score

log = logging.getLogger(__name__)

RAG_SCORE = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}
INVERSE_RAG_SCORE = {score: rag for rag, score in RAG_SCORE.items()}
PD_METRIC_ALIASES = {
    "Confidence Interval Test": "Confidence Interval",
}


def get_pd_model_column(cfg: dict) -> str:
    return cfg.get("data", {}).get("pd_model_column", "pd_model")


def _normalize_model_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _latest_snapshot(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if df.empty or date_column not in df.columns:
        return df.copy()
    latest_date = df[date_column].max()
    return df[df[date_column] == latest_date].copy()


def _metric_rag(thresholds: pd.DataFrame, metric: str, value: Any) -> str:
    if value is None or pd.isna(value) or thresholds.empty or "metric" not in thresholds.columns:
        return "N/A"

    threshold_metric = PD_METRIC_ALIASES.get(metric, metric)
    rows = thresholds[thresholds["metric"] == threshold_metric]
    if rows.empty:
        return "N/A"

    row = rows.iloc[0]
    red_condition = row.get("red_condition")
    if red_condition == "no_rag":
        return "Green"

    green_min = row.get("green_min")
    green_max = row.get("green_max")
    amber_min = row.get("amber_min")
    amber_max = row.get("amber_max")

    if red_condition == "outside amber range":
        if green_min <= value <= green_max:
            return "Green"
        if amber_min <= value <= amber_max:
            return "Amber"
        return "Red"
    if red_condition == "below amber_min":
        if value >= green_min:
            return "Green"
        if value >= amber_min:
            return "Amber"
        return "Red"
    if red_condition == "above amber_max":
        if value <= green_max:
            return "Green"
        if value <= amber_max:
            return "Amber"
        return "Red"
    if red_condition == "abs above amber_max":
        if abs(value) <= abs(green_max):
            return "Green"
        if abs(value) <= abs(amber_max):
            return "Amber"
        return "Red"
    return "N/A"


def _worst_rag(*rags: str) -> str:
    score = max((RAG_SCORE.get(rag, 0) for rag in rags), default=0)
    return INVERSE_RAG_SCORE.get(score, "N/A")


def _psi(current: pd.Series, prior: pd.Series, buckets: int = 10) -> float:
    current = pd.to_numeric(current, errors="coerce").dropna()
    prior = pd.to_numeric(prior, errors="coerce").dropna()
    if current.empty or prior.empty:
        return np.nan
    if prior.nunique() < 3:
        return 0.0

    breaks = np.unique(np.quantile(prior, np.linspace(0, 1, buckets + 1)))
    if len(breaks) < 3:
        return 0.0

    current_counts = pd.cut(current, bins=breaks, include_lowest=True).value_counts(normalize=True)
    prior_counts = pd.cut(prior, bins=breaks, include_lowest=True).value_counts(normalize=True)
    aligned = pd.DataFrame({"current": current_counts, "prior": prior_counts}).fillna(0.0001)
    aligned = aligned.replace(0, 0.0001)
    return float(((aligned["current"] - aligned["prior"]) * np.log(aligned["current"] / aligned["prior"])).sum())


def _rating_codes(current: pd.Series, prior: pd.Series) -> tuple[pd.Series, pd.Series]:
    rating_order = {"AAA": 1, "AA": 2, "A": 3, "BBB": 4, "BB": 5, "B": 6, "CCC/C": 7}
    current_numeric = pd.to_numeric(current, errors="coerce")
    prior_numeric = pd.to_numeric(prior, errors="coerce")
    if current_numeric.notna().all() and prior_numeric.notna().all():
        return current_numeric, prior_numeric
    return current.astype(str).map(rating_order), prior.astype(str).map(rating_order)


def _rating_migration_index(
    current: pd.DataFrame,
    prior: pd.DataFrame,
    id_column: str,
    rating_column: str,
) -> float:
    if current.empty or prior.empty or id_column not in current.columns or rating_column not in current.columns:
        return np.nan

    current_ratings = current[[id_column, rating_column]].rename(columns={rating_column: "current_rating"})
    prior_ratings = prior[[id_column, rating_column]].rename(columns={rating_column: "prior_rating"})
    merged = prior_ratings.merge(current_ratings, on=id_column, how="inner")
    if merged.empty:
        return np.nan

    current_codes, prior_codes = _rating_codes(merged["current_rating"], merged["prior_rating"])
    migration = (current_codes - prior_codes).abs().dropna()
    return float(migration.mean()) if not migration.empty else np.nan


def _normalize_crr_master_scale(crr_master_scale: pd.DataFrame) -> pd.DataFrame:
    if crr_master_scale.empty:
        return pd.DataFrame(columns=["crr", "min_pd", "max_pd"])

    normalized = crr_master_scale.copy()
    rename_map = {}
    for column in normalized.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key == "crr":
            rename_map[column] = "crr"
        elif key == "min_pd":
            rename_map[column] = "min_pd"
        elif key == "max_pd":
            rename_map[column] = "max_pd"
    normalized = normalized.rename(columns=rename_map)
    required = ["crr", "min_pd", "max_pd"]
    if any(column not in normalized.columns for column in required):
        return pd.DataFrame(columns=required)

    normalized = normalized[required].copy()
    for column in required:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=required).sort_values(["min_pd", "crr"]).reset_index(drop=True)
    return normalized


def _normalize_rag_assignment_pd(rag_assignment_pd: pd.DataFrame) -> pd.DataFrame:
    if rag_assignment_pd.empty:
        return pd.DataFrame()

    normalized = rag_assignment_pd.copy()
    first_column = normalized.columns[0]
    normalized = normalized.rename(columns={first_column: "notching_bucket"})
    normalized["notching_bucket"] = normalized["notching_bucket"].astype(str).str.strip()
    normalized = normalized[normalized["notching_bucket"] != ""].reset_index(drop=True)
    return normalized


def _map_pd_to_crr(probability: float, crr_master_scale: pd.DataFrame) -> float:
    if pd.isna(probability) or crr_master_scale.empty:
        return np.nan

    probability = float(probability)
    first = crr_master_scale.iloc[0]
    if probability <= float(first["min_pd"]):
        return float(first["crr"])

    for index, row in crr_master_scale.iterrows():
        lower = float(row["min_pd"])
        upper = float(row["max_pd"])
        is_last = index == len(crr_master_scale) - 1
        next_lower = float(crr_master_scale.iloc[index + 1]["min_pd"]) if not is_last else upper
        if probability >= lower and (probability < next_lower or (is_last and probability <= upper)):
            return float(row["crr"])

    return float(crr_master_scale.iloc[-1]["crr"])


def _pd_confidence_interval_bucket(value: float) -> str:
    if pd.isna(value):
        return ""
    value = float(value)
    if value < 0.05:
        return "p<5%"
    if value <= 0.90:
        return "5%<=p<=90%"
    if value <= 0.975:
        return "90%<p<=97.5%"
    return "p>97.5%"


def _pd_notching_bucket(value: float) -> str:
    if pd.isna(value):
        return ""
    value = float(value)
    if value > 2:
        return ">2"
    if np.isclose(value, 2.0):
        return "+2"
    if value < -2:
        return "<-2"
    if np.isclose(value, -2.0):
        return "-2"
    return "0 to +/-1"


def _pd_calibration_assignment_rag(
    rag_assignment_pd: pd.DataFrame,
    confidence_interval: float,
    signed_notching_difference: float,
) -> str:
    if rag_assignment_pd.empty or pd.isna(confidence_interval) or pd.isna(signed_notching_difference):
        return "N/A"

    confidence_bucket = _pd_confidence_interval_bucket(confidence_interval)
    notching_bucket = _pd_notching_bucket(signed_notching_difference)
    if not confidence_bucket or not notching_bucket:
        return "N/A"

    row = rag_assignment_pd[rag_assignment_pd["notching_bucket"] == notching_bucket]
    if row.empty or confidence_bucket not in rag_assignment_pd.columns:
        return "N/A"
    value = row.iloc[0].get(confidence_bucket)
    if pd.isna(value):
        return "N/A"
    return str(value).strip() or "N/A"


def _notching_components(
    df: pd.DataFrame,
    predicted_column: str,
    observed_column: str,
    crr_master_scale: pd.DataFrame,
) -> dict[str, float]:
    if df.empty or predicted_column not in df.columns or observed_column not in df.columns:
        return {
            "predicted_crr": np.nan,
            "observed_crr": np.nan,
            "signed_difference": np.nan,
            "absolute_difference": np.nan,
        }

    predicted = pd.to_numeric(df[predicted_column], errors="coerce")
    observed = pd.to_numeric(df[observed_column], errors="coerce")
    valid = predicted.notna() & observed.notna()
    predicted = predicted[valid]
    observed = observed[valid]
    if predicted.empty or observed.empty:
        return {
            "predicted_crr": np.nan,
            "observed_crr": np.nan,
            "signed_difference": np.nan,
            "absolute_difference": np.nan,
        }

    predicted_crr = _map_pd_to_crr(float(predicted.mean()), crr_master_scale)
    observed_crr = _map_pd_to_crr(float(observed.mean()), crr_master_scale)
    if pd.isna(predicted_crr) or pd.isna(observed_crr):
        return {
            "predicted_crr": np.nan,
            "observed_crr": np.nan,
            "signed_difference": np.nan,
            "absolute_difference": np.nan,
        }

    signed_difference = float(predicted_crr - observed_crr)
    return {
        "predicted_crr": float(predicted_crr),
        "observed_crr": float(observed_crr),
        "signed_difference": signed_difference,
        "absolute_difference": float(abs(signed_difference)),
    }


def _notching_test(
    df: pd.DataFrame,
    predicted_column: str,
    observed_column: str,
    crr_master_scale: pd.DataFrame,
) -> float:
    return _notching_components(df, predicted_column, observed_column, crr_master_scale)["absolute_difference"]


def _confidence_interval(
    df: pd.DataFrame,
    predicted_column: str,
    observed_column: str,
) -> float:
    """Return a stable dummy confidence interval value between 0% and 100%."""
    if df.empty or predicted_column not in df.columns or observed_column not in df.columns:
        return np.nan

    predicted = pd.to_numeric(df[predicted_column], errors="coerce")
    observed = pd.to_numeric(df[observed_column], errors="coerce")
    valid = predicted.notna() & observed.notna()
    predicted = predicted[valid]
    observed = observed[valid]
    if predicted.empty or observed.empty:
        return np.nan

    predicted_std = float(predicted.std(ddof=0)) if len(predicted) > 1 else 0.0
    observed_std = float(observed.std(ddof=0)) if len(observed) > 1 else 0.0
    seed = "|".join(
        [
            str(len(predicted)),
            f"{float(predicted.mean()):.6f}",
            f"{float(observed.mean()):.6f}",
            f"{predicted_std:.6f}",
            f"{observed_std:.6f}",
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return float(int(digest[:12], 16) / float(16**12 - 1))


def _pd_snapshot_metrics(
    current: pd.DataFrame,
    prior: pd.DataFrame,
    cfg: dict,
    predicted_column: str,
    observed_column: str,
    crr_master_scale: pd.DataFrame,
) -> dict[str, Any]:
    data_cfg = cfg.get("data", {})
    id_column = data_cfg.get("facility_id_column", "facility id")
    rating_column = data_cfg.get("rating_column", "rating_grade")
    current_quarter = ""
    if "_quarter" in current.columns:
        quarters = current["_quarter"].dropna().astype(str).unique().tolist()
        current_quarter = quarters[0] if quarters else ""

    predicted = pd.to_numeric(current[predicted_column], errors="coerce")
    observed = pd.to_numeric(current[observed_column], errors="coerce")
    valid = predicted.notna() & observed.notna()
    predicted = predicted[valid]
    observed = observed[valid]

    observed_rate = float(observed.mean()) if not observed.empty else np.nan
    predicted_rate = float(predicted.mean()) if not predicted.empty else np.nan
    ae_ratio = observed_rate / predicted_rate if predicted_rate and not pd.isna(predicted_rate) else np.nan

    accuracy_ratio = np.nan
    ks_statistic = np.nan
    kendall_value = np.nan
    if not observed.empty and observed.nunique() >= 2:
        try:
            accuracy_ratio = float(2 * roc_auc_score(observed, predicted) - 1)
        except ValueError:
            pass

        defaults = predicted[observed == 1]
        non_defaults = predicted[observed == 0]
        if not defaults.empty and not non_defaults.empty:
            ks_statistic = float(
                max(
                    abs((defaults <= threshold).mean() - (non_defaults <= threshold).mean())
                    for threshold in np.sort(predicted.unique())
                )
            )
        tau, _ = kendalltau(predicted, observed)
        if not np.isnan(tau):
            kendall_value = float(tau)

    prior_predicted = (
        pd.to_numeric(prior[predicted_column], errors="coerce")
        if predicted_column in prior.columns
        else pd.Series(dtype=float)
    )
    notching = _notching_components(current, predicted_column, observed_column, crr_master_scale)
    go_live_quarter = (
        current_quarter
        if current_quarter and "2019Q2" <= current_quarter <= "2019Q4"
        else ""
    )
    go_live_accuracy = accuracy_ratio if go_live_quarter else np.nan
    delta_accuracy_ratio = (
        (go_live_accuracy - accuracy_ratio) / go_live_accuracy
        if pd.notna(go_live_accuracy) and pd.notna(accuracy_ratio) and go_live_accuracy != 0
        else np.nan
    )

    return {
        "Actual / Expected Ratio": ae_ratio,
        "Accuracy Ratio": accuracy_ratio,
        "Go Live Accuracy Ratio": go_live_accuracy,
        "Delta Accuracy Ratio": delta_accuracy_ratio,
        "Go Live Quarter": go_live_quarter,
        "Gini Coefficient": accuracy_ratio,
        "KS Statistic": ks_statistic,
        "Brier Score": float(((observed - predicted) ** 2).mean()) if not observed.empty else np.nan,
        "Population Stability Index": _psi(predicted, prior_predicted),
        "Rating Migration Index": _rating_migration_index(current, prior, id_column, rating_column),
        "Notching Test": notching["absolute_difference"],
        "Signed Notching Difference": notching["signed_difference"],
        "Confidence Interval Test": _confidence_interval(current, predicted_column, observed_column),
        "Kendall's Tau": kendall_value,
    }


def _pd_horizon_columns(data_cfg: dict, horizon: str) -> tuple[str, str]:
    predicted_column = data_cfg.get(
        f"pd_predicted_{horizon}_column",
        data_cfg.get(
            f"pd_predicted_{horizon}_base_column",
            data_cfg.get("pd_predicted_column", f"CPD_{horizon}_base"),
        ),
    )
    observed_column = data_cfg.get(
        f"pd_observed_default_{horizon}_column",
        data_cfg.get("pd_observed_default_column", f"default flag {horizon}"),
    )
    return predicted_column, observed_column


def build_pd_overview_status_rows(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> list[dict[str, str]]:
    """Build PD status rows consumed by the monitoring Overview tab."""
    data_cfg = cfg.get("data", {})
    model_column = data_cfg.get("pd_model_column", "pd_model")
    segment_column = data_cfg.get("segment_column", "segment")
    date_column = data_cfg.get("date_column", "MONTH END-SNAPSHOT DATE")
    required = ["_quarter", model_column, segment_column, date_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        log.warning("PD overview columns not found: %s", missing)
        return []

    pd_thresholds = thresholds.get("pd_thresholds", pd.DataFrame())
    crr_master_scale = _normalize_crr_master_scale(thresholds.get("crr_master_scale", pd.DataFrame()))
    rag_assignment_pd = _normalize_rag_assignment_pd(thresholds.get("rag_assignment_pd", pd.DataFrame()))
    calibration_metrics = ["Confidence Interval Test", "Notching Test"]
    discriminatory_metrics = ["Accuracy Ratio", "Gini Coefficient", "KS Statistic", "Kendall's Tau"]
    performance_metrics = ["Brier Score", "Population Stability Index", "Rating Migration Index"]
    rows = []

    normalized = df.copy()
    normalized[model_column] = normalized[model_column].map(_normalize_model_name)
    normalized[segment_column] = normalized[segment_column].map(_normalize_model_name)
    normalized = normalized[(normalized[model_column] != "") & (normalized[segment_column] != "")]

    for horizon in ("1y", "2y"):
        predicted_column, observed_column = _pd_horizon_columns(data_cfg, horizon)
        horizon_missing = [
            column for column in (predicted_column, observed_column)
            if column not in normalized.columns
        ]
        if horizon_missing:
            log.warning("PD %s overview columns not found: %s", horizon, horizon_missing)
            continue

        for (model, segment), model_segment_df in normalized.groupby([model_column, segment_column]):
            quarters = sorted(model_segment_df["_quarter"].dropna().astype(str).unique())
            for index, quarter in enumerate(quarters):
                current = _latest_snapshot(model_segment_df[model_segment_df["_quarter"] == quarter], date_column)
                prior = pd.DataFrame(columns=current.columns)
                if index > 0:
                    prior = _latest_snapshot(
                        model_segment_df[model_segment_df["_quarter"] == quarters[index - 1]],
                        date_column,
                    )
                metrics = _pd_snapshot_metrics(
                    current,
                    prior,
                    cfg,
                    predicted_column,
                    observed_column,
                    crr_master_scale,
                )
                metric_rags = {metric: _metric_rag(pd_thresholds, metric, value) for metric, value in metrics.items()}
                calibration_rag = _pd_calibration_assignment_rag(
                    rag_assignment_pd,
                    metrics.get("Confidence Interval Test"),
                    metrics.get("Signed Notching Difference"),
                )
                if calibration_rag == "N/A":
                    calibration_rag = _worst_rag(*(metric_rags[metric] for metric in calibration_metrics))
                discriminatory_rag = _worst_rag(*(metric_rags[metric] for metric in discriminatory_metrics))
                performance_rag = _worst_rag(*(metric_rags[metric] for metric in performance_metrics))
                overall_rag = _worst_rag(calibration_rag, discriminatory_rag, performance_rag)
                rows.append(
                    {
                        "monitoring_period": quarter,
                        "time_horizon": horizon,
                        "model": model,
                        "model_group": "PD",
                        "segment": segment,
                        "overall_rag": overall_rag,
                        "pre_mitigation_rag": overall_rag,
                        "post_mitigation_rag": overall_rag,
                    }
                )
    return rows


def _build_threshold_summary(thresholds: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    summary = []
    for key, df in thresholds.items():
        if key == "crr_master_scale":
            continue
        if not isinstance(df, pd.DataFrame):
            continue
        rows = len(df)
        summary.append(
            {
                "threshold_key": key,
                "rows": rows,
                "cols": len(df.columns),
                "is_empty": rows == 0,
            }
        )
    summary.sort(key=lambda row: row["threshold_key"])
    return summary


def _build_model_rows(
    df: pd.DataFrame,
    model_column: str,
    id_column: str,
    thresholds: dict[str, pd.DataFrame],
) -> dict[str, dict[str, Any]]:
    if model_column not in df.columns:
        log.warning("PD model column '%s' not found in portfolio data.", model_column)
        return {}

    model_series = df[model_column].map(_normalize_model_name)
    model_series = model_series[model_series != ""]
    models = sorted(model_series.unique())

    by_model: dict[str, dict[str, Any]] = {}
    for model in models:
        model_df = df[model_series == model]
        rows = len(model_df)
        unique_accounts = int(model_df[id_column].nunique()) if id_column in model_df.columns else rows
        by_model[model] = {
            "model_name": model,
            "rows": rows,
            "unique_accounts": unique_accounts,
            "pct_of_portfolio": round(rows / len(df) * 100, 2) if len(df) else 0.0,
            "threshold_coverages": [],
        }

    return by_model


def _build_model_quarter_breakdown(
    df: pd.DataFrame,
    model_column: str,
    id_column: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    breakdown: dict[str, dict[str, dict[str, Any]]] = {}
    if model_column not in df.columns or "_quarter" not in df.columns:
        return breakdown

    normalized = df[[model_column, id_column, "_quarter"]].copy()
    normalized[model_column] = normalized[model_column].map(_normalize_model_name)
    normalized = normalized[normalized[model_column] != ""]

    for (model, quarter), group in normalized.groupby([model_column, "_quarter"]):
        rows = len(group)
        unique_accounts = int(group[id_column].nunique()) if id_column in group.columns else rows
        breakdown.setdefault(model, {})[quarter] = {
            "rows": rows,
            "unique_accounts": unique_accounts,
        }

    return breakdown


def _build_segment_values(df: pd.DataFrame, segment_column: str) -> list[str]:
    if segment_column not in df.columns:
        return []
    values = df[segment_column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return sorted(values.unique())


def _build_model_segment_quarter_breakdown(
    df: pd.DataFrame,
    model_column: str,
    segment_column: str,
    id_column: str,
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    breakdown: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    if model_column not in df.columns or segment_column not in df.columns or "_quarter" not in df.columns:
        return breakdown

    normalized = df[[model_column, segment_column, id_column, "_quarter"]].copy()
    normalized[model_column] = normalized[model_column].map(_normalize_model_name)
    normalized[segment_column] = normalized[segment_column].astype(str).str.strip()
    normalized = normalized[(normalized[model_column] != "") & (normalized[segment_column] != "")]

    for (model, segment, quarter), group in normalized.groupby([model_column, segment_column, "_quarter"]):
        rows = len(group)
        unique_accounts = int(group[id_column].nunique()) if id_column in group.columns else rows
        breakdown.setdefault(model, {}).setdefault(segment, {})[quarter] = {
            "rows": rows,
            "unique_accounts": unique_accounts,
        }

    return breakdown


def _build_pd_performance_observations(
    df: pd.DataFrame,
    model_column: str,
    segment_column: str,
    cfg: dict,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the compact row-level payload needed for interactive PD metrics."""
    data_cfg = cfg.get("data", {})
    rating_column = data_cfg.get("rating_column", "rating_grade")
    horizon_columns = {
        "1y": {
            "label": "1 year",
            "observed_column": data_cfg.get(
                "pd_observed_default_1y_column",
                data_cfg.get("pd_observed_default_column", "default flag 1y"),
            ),
            "predicted_column": data_cfg.get(
                "pd_predicted_1y_column",
                data_cfg.get("pd_predicted_1y_base_column", data_cfg.get("pd_predicted_column", "CPD_1y_base")),
            ),
            "ead_column": data_cfg.get("ead_predicted_1y_column", "EAD_1y_base"),
        },
        "2y": {
            "label": "2 years",
            "observed_column": data_cfg.get("pd_observed_default_2y_column", "default flag 2y"),
            "predicted_column": data_cfg.get(
                "pd_predicted_2y_column",
                data_cfg.get("pd_predicted_2y_base_column", "CPD_2y_base"),
            ),
            "ead_column": data_cfg.get("ead_predicted_2y_column", "EAD_2y_base"),
        },
        "nco_1y": {
            "label": "NCO PD 1 year",
            "observed_column": data_cfg.get(
                "pd_observed_default_1y_column",
                data_cfg.get("pd_observed_default_column", "default flag 1y"),
            ),
            "predicted_column": data_cfg.get(
                "pd_predicted_nco_1y_column",
                data_cfg.get("pd_predicted_nco_column", data_cfg.get("pd_predicted_nco_1y_base_column", "CPD_NCO_1y")),
            ),
            "ead_column": data_cfg.get("ead_predicted_1y_column", "EAD_1y_base"),
        },
    }
    required = [model_column, segment_column, "_quarter"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        log.warning("PD performance columns not found: %s", missing)
        return horizon_columns, []

    available_horizons = {}
    for horizon, columns in horizon_columns.items():
        observed_column = columns["observed_column"]
        if observed_column not in df.columns:
            log.warning("PD %s observed-default column not found: %s", horizon, observed_column)
            continue
        predicted_column = columns["predicted_column"]
        if predicted_column not in df.columns:
            log.warning("PD %s performance column not found: %s", horizon, predicted_column)
            continue
        available_horizons[horizon] = columns

    payload_columns = list(dict.fromkeys(required + (
        [rating_column] if rating_column in df.columns else []
    ) + [
        column
        for columns in available_horizons.values()
        for column in [columns["observed_column"], columns["predicted_column"], columns.get("ead_column")]
        if column
    ]))
    observations = df[payload_columns].copy()
    observations[model_column] = observations[model_column].map(_normalize_model_name)
    observations[segment_column] = observations[segment_column].astype(str).str.strip()
    observations = observations.dropna(subset=["_quarter"])
    observations = observations[
        (observations[model_column] != "")
        & (observations[segment_column] != "")
    ]

    for columns in available_horizons.values():
        observed_column = columns["observed_column"]
        observations[observed_column] = pd.to_numeric(observations[observed_column], errors="coerce")
        predicted_column = columns["predicted_column"]
        observations[predicted_column] = pd.to_numeric(observations[predicted_column], errors="coerce")
        ead_column = columns.get("ead_column")
        if ead_column and ead_column in observations.columns:
            observations[ead_column] = pd.to_numeric(observations[ead_column], errors="coerce")

    result = []
    for _, row in observations.iterrows():
        horizons = {}
        for horizon, columns in available_horizons.items():
            observed = row[columns["observed_column"]]
            if pd.isna(observed) or observed not in (0, 1):
                continue
            predicted = row[columns["predicted_column"]]
            if not pd.isna(predicted) and 0 <= predicted <= 1:
                ead_column = columns.get("ead_column")
                ead = row[ead_column] if ead_column and ead_column in observations.columns else np.nan
                horizons[horizon] = {
                    "observed": int(observed),
                    "predicted": round(float(predicted), 8),
                    "ead": round(float(ead), 2) if not pd.isna(ead) and ead >= 0 else None,
                }
        if horizons:
            result.append(
                {
                    "quarter": row["_quarter"],
                    "model": row[model_column],
                    "segment": row[segment_column],
                    "rating": _normalize_model_name(row[rating_column]) if rating_column in observations.columns else "",
                    "horizons": horizons,
                }
            )

    return horizon_columns, result


def _build_rating_migration_observations(
    df: pd.DataFrame,
    model_column: str,
    segment_column: str,
    cfg: dict,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return one worst-grade rating row per facility and quarter."""
    data_cfg = cfg.get("data", {})
    id_column = data_cfg.get("facility_id_column", "facility id")
    rating_column = data_cfg.get("rating_column", "rating_grade")
    required = [id_column, model_column, segment_column, "_quarter", rating_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        log.warning("Rating migration columns not found: %s", missing)
        return [], []

    observations = df[required].copy()
    observations[id_column] = observations[id_column].map(_normalize_model_name)
    observations[model_column] = observations[model_column].map(_normalize_model_name)
    observations[segment_column] = observations[segment_column].astype(str).str.strip()
    observations["_rating_numeric"] = pd.to_numeric(observations[rating_column], errors="coerce")
    observations = observations.dropna(subset=["_quarter", "_rating_numeric"])
    observations = observations[
        (observations[id_column] != "")
        & (observations[model_column] != "")
        & (observations[segment_column] != "")
    ]

    # Where a facility has multiple rows in a quarter, retain the worst grade.
    observations = observations.sort_values("_rating_numeric")
    observations = observations.groupby(["_quarter", id_column], as_index=False).tail(1)

    ratings = sorted(observations["_rating_numeric"].unique())

    def rating_label(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    return (
        [rating_label(value) for value in ratings],
        [
            {
                "quarter": row["_quarter"],
                "account": row[id_column],
                "model": row[model_column],
                "segment": row[segment_column],
                "rating": rating_label(row["_rating_numeric"]),
            }
            for _, row in observations.iterrows()
        ],
    )


def _load_pd_mev_catalog() -> dict[str, Any]:
    """Load the dummy MEV time-series catalog used by the PD MEV range section."""
    path = Path(__file__).resolve().parents[1] / "mev_dummy_data.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.warning("PD MEV dummy data file not found: %s", path)
        return {}
    except json.JSONDecodeError as exc:
        log.warning("PD MEV dummy data file could not be parsed: %s", exc)
        return {}

    if not isinstance(payload, dict):
        log.warning("PD MEV dummy data must be a model-keyed JSON object.")
        return {}

    catalog: dict[str, Any] = {}
    for raw_model_name, raw_model_payload in payload.items():
        if not isinstance(raw_model_payload, dict):
            continue

        model_name = _normalize_model_name(raw_model_name)
        if not model_name:
            continue

        raw_mevs = raw_model_payload.get("mevs", {})
        if not isinstance(raw_mevs, dict):
            raw_mevs = {}

        mevs: dict[str, Any] = {}
        for raw_mev_name, raw_mev_payload in raw_mevs.items():
            if not isinstance(raw_mev_payload, dict):
                continue

            dev_range = raw_mev_payload.get("dev_range", {})
            time_series = raw_mev_payload.get("time_series", {})
            if not isinstance(dev_range, dict):
                dev_range = {}
            if not isinstance(time_series, dict):
                time_series = {}

            clean_range = {
                "min": pd.to_numeric(dev_range.get("min"), errors="coerce"),
                "max": pd.to_numeric(dev_range.get("max"), errors="coerce"),
                "mean": pd.to_numeric(dev_range.get("mean"), errors="coerce"),
                "2std_lower": pd.to_numeric(dev_range.get("2std_lower"), errors="coerce"),
                "2std_upper": pd.to_numeric(dev_range.get("2std_upper"), errors="coerce"),
                "development_date": str(dev_range.get("development_date") or ""),
            }
            clean_range = {
                key: (round(float(value), 6) if pd.notna(value) else None)
                for key, value in clean_range.items()
                if key != "development_date"
            } | {"development_date": clean_range["development_date"]}

            clean_series = {
                str(period): round(float(value), 6)
                for period, value in time_series.items()
                if pd.notna(pd.to_numeric(value, errors="coerce"))
            }
            mevs[str(raw_mev_name).strip()] = {
                "dev_range": clean_range,
                "time_series": clean_series,
            }

        catalog[model_name] = {
            "segments": [
                str(segment).strip()
                for segment in raw_model_payload.get("segments", [])
                if str(segment).strip()
            ],
            "severe_scenario_date": str(raw_model_payload.get("severe_scenario_date") or ""),
            "mevs": mevs,
        }

    return catalog


def build_monitoring_pd_models(
    df: pd.DataFrame,
    thresholds: dict[str, pd.DataFrame],
    cfg: dict,
) -> dict[str, Any]:
    model_column = get_pd_model_column(cfg)
    segment_column = cfg.get("data", {}).get("segment_column", "segment")
    id_column = cfg.get("population", {}).get("id_column", "facility id")
    latest_quarter = ""
    if "_quarter" in df.columns and not df["_quarter"].isna().all():
        quarters = sorted(set(df["_quarter"]))
        latest_quarter = quarters[-1] if quarters else ""

    model_rows = _build_model_rows(df, model_column, id_column, thresholds)
    model_quarter_breakdown = _build_model_quarter_breakdown(df, model_column, id_column)
    segment_names = _build_segment_values(df, segment_column)
    model_segment_quarter = _build_model_segment_quarter_breakdown(df, model_column, segment_column, id_column)
    performance_horizons, performance_observations = _build_pd_performance_observations(
        df, model_column, segment_column, cfg
    )
    rating_values, rating_migration_observations = _build_rating_migration_observations(
        df, model_column, segment_column, cfg
    )
    mev_catalog = _load_pd_mev_catalog()

    return {
        "model_column": model_column,
        "model_names": list(model_rows.keys()),
        "segment_column": segment_column,
        "segment_values": segment_names,
        "latest_quarter": latest_quarter,
        "portfolio_records": len(df),
        "portfolio_unique_accounts": int(df[id_column].nunique()) if id_column in df.columns else len(df),
        "threshold_summary": _build_threshold_summary(thresholds),
        "by_model": model_rows,
        "by_model_by_quarter": model_quarter_breakdown,
        "by_model_by_segment_by_quarter": model_segment_quarter,
        "performance_horizons": performance_horizons,
        "performance_observations": performance_observations,
        "rating_values": rating_values,
        "rating_migration_observations": rating_migration_observations,
        "mev_source_file": "mev_dummy_data.json",
        "mev_catalog": mev_catalog,
    }
