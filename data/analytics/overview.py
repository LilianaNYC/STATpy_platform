"""Overview-page data helpers built on the PD performance data payload."""

from __future__ import annotations

from collections import Counter
from typing import Any

import polars as pl

from .calculations import (
    PdFilterContext,
    calculate_pd_discrimination_section_rag,
    calculate_pd_metric_rag,
    calculate_pd_overview_performance_rag,
    calculate_pd_rag_metrics_for_horizon,
    get_pd_crr_master_scale,
    get_pd_thresholds,
    get_worst_pd_rag,
)

RAG_SCORE = {"Green": 1, "N/A": 2, "Amber": 2, "Red": 3}
INVERSE_RAG_SCORE = {score: rag for rag, score in RAG_SCORE.items()}
RAG_COLUMNS = [
    "Calibration Conservatism RAG",
    "Discriminatory Power RAG",
    "Performance RAG",
    "Overall RAG",
    "Pre-Mitigation RAG",
    "Post-Mitigation RAG",
]


def effective_rag(rag: str | None) -> str:
    return "Amber" if rag == "N/A" else rag or "N/A"


def display_rag(rag: str | None) -> str:
    return "Fallback Amber" if rag == "N/A" else rag or "N/A"


def _latest_rows(rows: list[dict[str, Any]], period: str | None = None) -> list[dict[str, Any]]:
    if not rows:
        return []
    selected_period = period if period and period != "All" else max(row["Monitoring Period"] for row in rows)
    return [row for row in rows if row["Monitoring Period"] == selected_period]


def _worst_rag_from_rows(rows: list[dict[str, Any]], column: str) -> str:
    return max(
        (row.get(column, "N/A") for row in rows),
        key=lambda rag: (RAG_SCORE.get(effective_rag(rag), 0), 0 if rag == "N/A" else 1),
        default="N/A",
    )


def _metric_rag_values(thresholds: list[dict[str, Any]], values: dict[str, Any], metrics: list[str]) -> list[str]:
    return [calculate_pd_metric_rag(thresholds, metric, values.get(metric)) for metric in metrics]


def _pd_overview_rows(data: dict) -> list[dict[str, Any]]:
    rows = []
    thresholds = get_pd_thresholds(data["monitoring_thresholds"])
    crr_scale = get_pd_crr_master_scale(data["monitoring_thresholds"])

    for quarter in data["quarters"]:
        for model_name in data["model_names"]:
            for segment in data["segment_values"]:
                ctx = PdFilterContext(
                    quarters=data["quarters"],
                    models={model_name},
                    segment=segment,
                    monitoring_point=quarter,
                )

                values = calculate_pd_rag_metrics_for_horizon(
                    data["performance_observations"],
                    data["rating_migration_observations"],
                    quarter,
                    "1y",
                    ctx,
                    crr_scale,
                )
                balance_values = calculate_pd_rag_metrics_for_horizon(
                    data["performance_observations"],
                    data["rating_migration_observations"],
                    quarter,
                    "nco_1y",
                    ctx,
                    crr_scale,
                )

                calibration_rag = get_worst_pd_rag(
                    _metric_rag_values(thresholds, values, ["Confidence Interval Test", "Notching Test"])
                )
                discrimination_rag = calculate_pd_discrimination_section_rag(thresholds, values)
                performance_rag = get_worst_pd_rag(
                    _metric_rag_values(
                        thresholds,
                        values,
                        ["Brier Score", "Population Stability Index", "Rating Migration Index"],
                    )
                )
                balance_sheet_rag = get_worst_pd_rag(
                    _metric_rag_values(thresholds, balance_values, ["Confidence Interval Test", "Notching Test"])
                )
                overall_rag = calculate_pd_overview_performance_rag(
                    calibration_rag,
                    discrimination_rag,
                    balance_sheet_rag,
                )["rag"]

                rows.append(
                    {
                        "Monitoring Period": quarter,
                        "Model Group": "PD",
                        "Model": model_name,
                        "Segment": segment,
                        "Calibration Conservatism RAG": calibration_rag,
                        "Discriminatory Power RAG": discrimination_rag,
                        "Performance RAG": performance_rag,
                        "Overall RAG": overall_rag,
                        "Pre-Mitigation RAG": overall_rag,
                        "Post-Mitigation RAG": overall_rag,
                    }
                )

    return rows


def _lgd_ead_overview_rows(data: dict) -> list[dict[str, Any]]:
    portfolio = data["portfolio"]
    rows = []

    definitions = [
        ("LGD", "lgd_model", "LGD_1y_base"),
        ("EAD", "ead_model", "EAD_1y_base"),
    ]
    for model_group, model_col, value_col in definitions:
        if model_col not in portfolio.columns or value_col not in portfolio.columns:
            continue

        historical = (
            portfolio.group_by(model_col)
            .agg(
                pl.col(value_col).quantile(0.75).alias("p75"),
                pl.col(value_col).quantile(0.90).alias("p90"),
            )
            .iter_rows(named=True)
        )
        bands = {row[model_col]: row for row in historical}

        grouped = (
            portfolio.group_by(["_quarter", model_col, "Portfolio"])
            .agg(pl.col(value_col).mean().alias("mean_value"))
            .sort(["_quarter", model_col, "Portfolio"])
        )
        for row in grouped.iter_rows(named=True):
            model_name = row[model_col] or f"{model_group} Model"
            value = row["mean_value"]
            band = bands.get(model_name, {})

            if model_group == "LGD":
                rag = "Green" if value <= 0.45 else "Amber" if value <= 0.60 else "Red"
            else:
                p75 = band.get("p75")
                p90 = band.get("p90")
                rag = "Green" if p75 is None or value <= p75 else "Amber" if p90 is None or value <= p90 else "Red"

            rows.append(
                {
                    "Monitoring Period": row["_quarter"],
                    "Model Group": model_group,
                    "Model": model_name,
                    "Segment": row["Portfolio"],
                    "Calibration Conservatism RAG": "N/A",
                    "Discriminatory Power RAG": "N/A",
                    "Performance RAG": rag,
                    "Overall RAG": rag,
                    "Pre-Mitigation RAG": rag,
                    "Post-Mitigation RAG": rag,
                }
            )

    return rows


def build_overview_rows(data: dict) -> list[dict[str, Any]]:
    return _pd_overview_rows(data) + _lgd_ead_overview_rows(data)


def filter_overview_rows(
    rows: list[dict[str, Any]],
    monitoring_period: str = "All",
    model_group: str = "All",
    model: str | list[str] | tuple[str, ...] | set[str] = "All",
    segment: str = "All",
) -> list[dict[str, Any]]:
    filtered = rows
    if monitoring_period != "All":
        filtered = [row for row in filtered if row["Monitoring Period"] == monitoring_period]
    if model_group != "All":
        filtered = [row for row in filtered if row["Model Group"] == model_group]
    if isinstance(model, (list, tuple, set)):
        selected_models = {str(value) for value in model if value not in {"All", "", None}}
        if selected_models:
            filtered = [row for row in filtered if row["Model"] in selected_models]
    elif model != "All":
        filtered = [row for row in filtered if row["Model"] == model]
    if segment != "All":
        filtered = [row for row in filtered if row["Segment"] == segment]
    return filtered


def overview_filter_options(rows: list[dict[str, Any]], model_group: str = "All") -> dict[str, list[str]]:
    scoped = rows if model_group == "All" else [row for row in rows if row["Model Group"] == model_group]
    return {
        "periods": ["All"] + sorted({row["Monitoring Period"] for row in rows}),
        "groups": ["All"] + sorted({row["Model Group"] for row in rows}),
        "models": ["All"] + sorted({row["Model"] for row in scoped}),
        "segments": ["All"] + sorted({row["Segment"] for row in rows}),
    }


def overview_summary(rows: list[dict[str, Any]], monitoring_period: str = "All") -> dict[str, int]:
    current_rows = _latest_rows(rows, monitoring_period)
    by_model = {}
    for row in current_rows:
        key = (row["Model Group"], row["Model"])
        rag = effective_rag(row["Overall RAG"])
        if key not in by_model or RAG_SCORE.get(rag, 0) >= RAG_SCORE.get(by_model[key], 0):
            by_model[key] = effective_rag(row["Overall RAG"])

    counts = Counter(by_model.values())
    red = counts.get("Red", 0)
    amber = counts.get("Amber", 0)
    green = counts.get("Green", 0)
    return {
        "models": len(by_model),
        "red": red,
        "amber": amber,
        "green": green,
        "breaches": red + amber,
    }


def heatmap_rows(rows: list[dict[str, Any]], monitoring_period: str = "All") -> list[dict[str, Any]]:
    current_rows = _latest_rows(rows, monitoring_period)
    output = []
    for model_key in sorted({(row["Model Group"], row["Model"]) for row in current_rows}):
        model_rows = [row for row in current_rows if (row["Model Group"], row["Model"]) == model_key]
        selected_period = model_rows[0]["Monitoring Period"] if model_rows else ""
        output.append(
            {
                "Monitoring Period": selected_period,
                "Model Group": model_key[0],
                "Model": model_key[1],
                **{column: _worst_rag_from_rows(model_rows, column) for column in RAG_COLUMNS},
            }
        )
    return output


def top_findings(rows: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    def finding_rank(rag: str | None) -> int:
        if effective_rag(rag) == "Red":
            return 0
        if rag == "Amber":
            return 1
        if rag == "N/A":
            return 2
        return 3

    findings = []
    for row in rows:
        for column in RAG_COLUMNS:
            rag = row.get(column)
            if effective_rag(rag) in {"Red", "Amber"}:
                findings.append(
                    {
                        "Monitoring Period": row.get("Monitoring Period", "-"),
                        "Model Group": row["Model Group"],
                        "Model": row["Model"],
                        "Metric": column,
                        "Current": display_rag(rag),
                        "Threshold": "Heatmap finding",
                        "RAG": rag,
                    }
                )
    findings.sort(
        key=lambda row: (
            finding_rank(row["RAG"]),
            row["Model Group"],
            row["Model"],
            row["Metric"],
        )
    )
    return findings[:limit] if limit is not None else findings


def ecl_scenario_rows(data: dict) -> list[dict[str, Any]]:
    portfolio = data["portfolio"]
    if not {"_quarter", "ecl_amount_base", "ecl_amount_severe"}.issubset(set(portfolio.columns)):
        return []
    grouped = (
        portfolio.group_by("_quarter")
        .agg(
            pl.col("ecl_amount_base").sum().alias("baseline"),
            pl.col("ecl_amount_severe").sum().alias("severe"),
        )
        .with_columns(
            (pl.col("baseline") * 1.12).alias("adverse"),
            (pl.col("baseline") * 0.93).alias("upside"),
        )
        .sort("_quarter")
    )
    return grouped.to_dicts()


def ecl_coverage_rows(data: dict) -> list[dict[str, Any]]:
    portfolio = data["portfolio"]
    if not {"_quarter", "ecl_amount_base", "Balance"}.issubset(set(portfolio.columns)):
        return []
    grouped = (
        portfolio.group_by("_quarter")
        .agg(
            pl.col("ecl_amount_base").sum().alias("ecl"),
            pl.col("Balance").sum().alias("balance"),
        )
        .with_columns((pl.col("ecl") / pl.col("balance")).alias("coverage"))
        .sort("_quarter")
    )
    return grouped.to_dicts()
