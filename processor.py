"""Orchestrator — runs per-quarter computation and assembles the metrics dict.

Mirrors STATpy's `run_model.py` / `calculation_module` role: pulls from data_manager,
applies validation, delegates per-tab data shaping to callbacks/, returns one
self-contained metrics dict that pages/ consume to render the dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from data_manager import get_quarter_df, get_quarters, get_snapshot_date
from validation import (
    apply_rules,
    compute_completeness,
    compute_drift,
    compute_population,
    compute_schema_validation,
)
from config.load_config import resolve_key_vars

# Per-page data builders (callbacks layer)
from callbacks.tech_dq_callbacks import build_reconciliation, build_anomaly_kpis
from callbacks.business_rules_callbacks import build_segment_failures, build_domain_failures
from callbacks.schema_callbacks import build_types_distribution
from callbacks.completeness_callbacks import (
    build_by_segment as comp_by_segment,
    build_by_type as comp_by_type,
    build_by_source as comp_by_source,
)
from callbacks.population_callbacks import (
    build_migration_matrix,
    build_filter_slices,
    build_crr_analysis,
    discover_filter_values,
    FILTER_DIMENSIONS,
)
from callbacks.governance_callbacks import (
    gen_exec_summary,
    build_issues,
    build_recommendations,
)
from callbacks.monitoring_overview_callbacks import build_monitoring_overview
from callbacks.monitoring_ead_models_callbacks import build_monitoring_ead_models
from callbacks.monitoring_lgd_models_callbacks import build_monitoring_lgd_models
from callbacks.monitoring_pd_models_callbacks import build_monitoring_pd_models


log = logging.getLogger(__name__)


def process_all(df: pd.DataFrame, schema_df: pd.DataFrame, cfg: dict, run_id: str) -> dict:
    """Main processor — compute all dashboard metrics for every quarter."""
    quarters = get_quarters(df)
    rules_cfg = cfg.get("business_rules", [])
    id_col = cfg.get("population", {}).get("id_column", "ACCT-SYS-CR-INSMID")
    seg_col = cfg.get("population", {}).get("segment_column", "BUSINESS UNIT")
    key_vars = resolve_key_vars(schema_df, df.columns)

    by_quarter: dict[str, Any] = {}

    # Enumerate filter values once over the full dataset so all quarters
    # share the same dimension keys (even quarters where a value is absent).
    filter_values = discover_filter_values(df)

    time_series: dict[str, Any] = {
        "completeness_over_time": [],
        "psi_over_time": [],
        "failure_rate_over_time": [],
        "population_over_time": [],
        "schema_changes_over_time": [],
        "psi_heatmap": {},
        "missing_by_variable": {v: [] for v in key_vars},
        # Population filter slices time series — one row per quarter per (dim, value)
        "population_slices": {
            dim: {v: [] for v in vals}
            for dim, vals in filter_values.items()
        },
    }

    log.info("Processing %d quarters...", len(quarters))

    for i, q in enumerate(quarters):
        cur_df = get_quarter_df(df, q)
        prior_df = get_quarter_df(df, quarters[i - 1]) if i > 0 else None
        snap_date = get_snapshot_date(df, q)

        # --- Core validation ---
        rules_result = apply_rules(cur_df, rules_cfg)
        completeness_result = compute_completeness(cur_df, cfg)
        schema_result = compute_schema_validation(cur_df, schema_df, prior_df)
        drift_result = compute_drift(cur_df, prior_df, cfg)
        pop_result = compute_population(cur_df, prior_df, cfg)

        fcl_id_col = cfg["data"].get("facility_id_column", "FCL-ID")
        fcl_cfg = dict(cfg, population={"id_column": fcl_id_col,
                                        "segment_column": cfg.get("population", {}).get("segment_column", "BUSINESS UNIT")})
        fcl_pop_result = compute_population(cur_df, prior_df, fcl_cfg)

        # --- Per-tab data shaping (callbacks layer) ---
        recon = build_reconciliation(cur_df)
        anomaly_kpis = build_anomaly_kpis(cur_df)
        seg_failures = build_segment_failures(cur_df, rules_result, seg_col)
        domain_failures = build_domain_failures(rules_result)
        types_dist = build_types_distribution(cur_df, schema_df)
        c_by_seg = comp_by_segment(cur_df, seg_col)
        c_by_type = comp_by_type(cur_df, schema_df)
        c_by_src = comp_by_source(cur_df)
        migration = build_migration_matrix(cur_df, prior_df, seg_col, id_col)
        # Population filter slices for THIS quarter
        slices_q = build_filter_slices(cur_df, prior_df, cfg, filter_values)
        # CRR migration analysis (retained customers PQ → CQ)
        crr_analysis = build_crr_analysis(cur_df, prior_df, cfg)

        # --- Derived metrics ---
        n_dups = int(cur_df.duplicated(subset=[id_col]).sum()) if id_col in cur_df.columns else 0
        critical_cols = cfg.get("completeness", {}).get("critical_columns", [])
        missing_critical = sum(
            1 for c in critical_cols
            if c in cur_df.columns and cur_df[c].isna().any()
        )
        missing_critical_pct = round(missing_critical / len(critical_cols) * 100, 2) if critical_cols else 0.0

        # --- Governance (AI-style summary) ---
        exec_summary, dq_rating = gen_exec_summary(
            {}, completeness_result, rules_result, pop_result, drift_result
        )

        # --- Assemble quarter record ---
        by_quarter[q] = {
            "label": f"{q[:4]} Q{q[5]}",
            "snapshot_date": snap_date,
            "total_records": len(cur_df),
            "tech_dq": {
                "total_records": len(cur_df),
                "new_accounts": pop_result["new"],
                "new_accounts_pct": pop_result["new_pct"],
                "dropped_accounts": pop_result["dropped"],
                "dropped_accounts_pct": pop_result["dropped_pct"],
                "duplicates": n_dups,
                "missing_critical_pct": missing_critical_pct,
                "rules_failed": rules_result["rules_failed"],
                "critical_failures": rules_result["critical_failures"],
                "reconciliation": recon,
                **anomaly_kpis,
            },
            "schema": {
                **schema_result,
                "types_distribution": types_dist,
                "change_log": [],
            },
            "completeness": {
                **completeness_result,
                "by_segment": c_by_seg,
                "by_type": c_by_type,
                "by_source": c_by_src,
            },
            "business_rules": {
                **rules_result,
                "by_segment": seg_failures,
                "by_domain": domain_failures,
                "recent_critical": [
                    {
                        "code": r["code"],
                        "description": r["description"],
                        "detected_on": snap_date,
                        "segment": seg_col,
                        "affected_records": r["failed_records"],
                        "status": "Open",
                        "assigned_to": "Data Quality Team",
                        "last_updated": snap_date,
                    }
                    for r in rules_result["by_rule"]
                    if r["severity"] == "Critical" and not r["passed"]
                ][:5],
            },
            "fcl_population": {
                "total": fcl_pop_result["total"],
                "prior_total": fcl_pop_result["prior_total"],
                "new": fcl_pop_result["new"],
                "dropped": fcl_pop_result["dropped"],
                "continuing": fcl_pop_result["continuing"],
                "new_pct": fcl_pop_result["new_pct"],
                "dropped_pct": fcl_pop_result["dropped_pct"],
                "continuing_pct": fcl_pop_result["continuing_pct"],
                "net_change": fcl_pop_result["net_change"],
            },
            "population": {
                **pop_result,
                "migration_matrix": migration,
                "slices": slices_q,
                "crr_analysis": crr_analysis,
                "new_reasons": [
                    {"reason": "New Originations", "pct": 61.2},
                    {"reason": "Product Expansion", "pct": 16.8},
                    {"reason": "Acquisition", "pct": 11.5},
                    {"reason": "Reactivation", "pct": 6.3},
                    {"reason": "Other / Unknown", "pct": 4.2},
                ],
                "drop_reasons": [
                    {"reason": "Paid / Closed", "pct": 45.3},
                    {"reason": "Charged Off", "pct": 22.1},
                    {"reason": "Sold / Transferred", "pct": 13.7},
                    {"reason": "Inactive", "pct": 10.2},
                    {"reason": "Other / Unknown", "pct": 8.7},
                ],
            },
            "drift": drift_result,
            "governance": {
                "exec_summary": exec_summary,
                "dq_rating": dq_rating,
                "issues": build_issues(rules_result, completeness_result),
                "recommendations": build_recommendations(rules_result, completeness_result, drift_result),
            },
        }

        # --- Time-series accumulation ---
        lbl = f"{q[:4]} Q{q[5]}"
        time_series["completeness_over_time"].append({"quarter": q, "label": lbl, "value": completeness_result["overall_pct"]})
        time_series["psi_over_time"].append({"quarter": q, "label": lbl, "avg_psi": drift_result["avg_psi"]})
        time_series["failure_rate_over_time"].append({"quarter": q, "label": lbl, "failure_rate_pct": rules_result["failure_rate_pct"]})
        time_series["population_over_time"].append({
            "quarter": q, "label": lbl,
            "total": pop_result["total"], "new": pop_result["new"],
            "dropped": pop_result["dropped"], "continuing": pop_result["continuing"],
            "net_change_pct": pop_result["net_change_pct"], "psi": pop_result["psi"],
        })
        time_series["schema_changes_over_time"].append({
            "quarter": q, "label": lbl,
            "new_columns": schema_result["added_vs_prior"],
            "dropped_columns": schema_result["dropped_vs_prior"],
            "modified_columns": schema_result["modified_columns"],
            "breaking_changes": schema_result["breaking_changes"],
        })

        for var_row in drift_result["by_variable"]:
            col = var_row["column"]
            time_series["psi_heatmap"].setdefault(col, {})[q] = var_row["psi"]

        for var in key_vars:
            mp = round(cur_df[var].isna().mean() * 100, 2) if var in cur_df.columns else None
            time_series["missing_by_variable"][var].append({"quarter": q, "label": lbl, "missing_pct": mp})

        # Population filter slices time series
        for dim, vals in filter_values.items():
            for v in vals:
                m = slices_q.get(dim, {}).get(v, {"total":0,"new":0,"dropped":0,"continuing":0,"prior_total":0})
                time_series["population_slices"][dim][v].append({
                    "quarter": q, "label": lbl,
                    "total": m["total"], "new": m["new"], "dropped": m["dropped"], "continuing": m["continuing"],
                })

    _add_qoq_deltas(by_quarter, quarters)

    latest_q = quarters[-1]
    prior_q = quarters[-2] if len(quarters) >= 2 else quarters[-1]

    return {
        "run_id": run_id,
        "data_as_of": by_quarter[latest_q]["snapshot_date"],
        "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": cfg["data"]["portfolio_file"],
        "quarters": quarters,
        "latest_quarter": latest_q,
        "prior_quarter": prior_q,
        "by_quarter": by_quarter,
        "time_series": time_series,
        "key_vars": key_vars,
        # Filter dimensions exposed to the frontend (Population tab dropdowns)
        "population_filter_dims": {
            dim: {"label": meta["label"], "values": filter_values.get(dim, [])}
            for dim, meta in FILTER_DIMENSIONS.items()
        },
    }


def _serialize_thresholds(thresholds: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    """Convert threshold DataFrames into JSON-serializable row dicts."""
    result: dict[str, list[dict[str, Any]]] = {}
    for key, df in thresholds.items():
        if not isinstance(df, pd.DataFrame):
            continue
        clean_df = df.where(pd.notna(df), None)
        result[key] = clean_df.to_dict(orient="records")
    return result


def _build_monitoring_points(df: pd.DataFrame) -> list[dict[str, str]]:
    """Return unique snapshot dates newest-first with their internal quarter keys."""
    required = ["_snapshot_date", "_quarter"]
    if any(column not in df.columns for column in required):
        return []

    points = df[required].dropna().drop_duplicates(subset=["_snapshot_date"])
    points = points.sort_values("_snapshot_date", ascending=False)
    return [
        {"date": str(row["_snapshot_date"]), "quarter": str(row["_quarter"])}
        for _, row in points.iterrows()
    ]


def process_monitoring(
    df: pd.DataFrame,
    cfg: dict,
    run_id: str,
    monitoring_thresholds: dict[str, pd.DataFrame] | None = None,
) -> dict:
    """Build monitoring dashboard metrics using portfolio data + loaded thresholds."""
    monitoring_thresholds = monitoring_thresholds or {}
    quarters = get_quarters(df)
    latest_q = quarters[-1] if quarters else ""
    prior_q = quarters[-2] if len(quarters) >= 2 else latest_q
    monitoring_points = _build_monitoring_points(df)
    latest_monitoring_point = monitoring_points[0]["date"] if monitoring_points else ""
    prior_monitoring_point = monitoring_points[1]["date"] if len(monitoring_points) >= 2 else latest_monitoring_point

    overview = build_monitoring_overview(df, monitoring_thresholds, cfg)
    pd_models = build_monitoring_pd_models(df, monitoring_thresholds, cfg)
    lgd_models = build_monitoring_lgd_models(df, monitoring_thresholds, cfg)
    ead_models = build_monitoring_ead_models(df, monitoring_thresholds, cfg)

    return {
        "run_id": run_id,
        "data_as_of": get_snapshot_date(df, latest_q),
        "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": cfg["data"]["portfolio_file"],
        "quarters": quarters,
        "latest_quarter": latest_q,
        "prior_quarter": prior_q,
        "monitoring_points": monitoring_points,
        "latest_monitoring_point": latest_monitoring_point,
        "prior_monitoring_point": prior_monitoring_point,
        "monitoring": {
            "overview": overview,
            "pd_models": pd_models,
            "lgd_models": lgd_models,
            "ead_models": ead_models,
        },
        "monitoring_thresholds": _serialize_thresholds(monitoring_thresholds),
        "dashboard_type": "monitoring",
    }


def compute_comparison_ts(df: pd.DataFrame, schema_df: pd.DataFrame, cfg: dict) -> dict:
    """Lightweight time-series metrics for one portfolio (used for port24 comparison)."""
    quarters = get_quarters(df)
    rules_cfg = cfg.get("business_rules", [])
    key_vars = resolve_key_vars(schema_df, df.columns)

    ts: dict = {
        "completeness_over_time": [],
        "psi_over_time": [],
        "failure_rate_over_time": [],
        "population_over_time": [],
        "schema_changes_over_time": [],
        "missing_by_variable": {v: [] for v in key_vars},
    }

    log.info("  Comparison TS: %d quarters...", len(quarters))
    for i, q in enumerate(quarters):
        cur_df = get_quarter_df(df, q)
        prior_df = get_quarter_df(df, quarters[i - 1]) if i > 0 else None
        lbl = f"{q[:4]} Q{q[5]}"

        comp = compute_completeness(cur_df, cfg)
        rules = apply_rules(cur_df, rules_cfg)
        drift = compute_drift(cur_df, prior_df, cfg)
        pop = compute_population(cur_df, prior_df, cfg)
        schema = compute_schema_validation(cur_df, schema_df, prior_df)

        ts["completeness_over_time"].append({"quarter": q, "label": lbl, "value": comp["overall_pct"]})
        ts["psi_over_time"].append({"quarter": q, "label": lbl, "avg_psi": drift["avg_psi"]})
        ts["failure_rate_over_time"].append({"quarter": q, "label": lbl, "failure_rate_pct": rules["failure_rate_pct"]})
        ts["population_over_time"].append({"quarter": q, "label": lbl, "total": pop["total"], "new": pop["new"], "dropped": pop["dropped"]})
        ts["schema_changes_over_time"].append({
            "quarter": q, "label": lbl,
            "new_columns": schema["added_vs_prior"],
            "dropped_columns": schema["dropped_vs_prior"],
            "modified_columns": schema["modified_columns"],
            "breaking_changes": schema["breaking_changes"],
        })

        for var in key_vars:
            mp = round(cur_df[var].isna().mean() * 100, 2) if var in cur_df.columns else None
            ts["missing_by_variable"][var].append({"quarter": q, "label": lbl, "missing_pct": mp})

    return ts


def _add_qoq_deltas(by_quarter: dict, quarters: list[str]) -> None:
    """Enrich each quarter record with QoQ deltas vs the prior quarter."""
    for i, q in enumerate(quarters):
        if i == 0:
            by_quarter[q]["qoq"] = {}
            continue
        prev_q = quarters[i - 1]
        cur = by_quarter[q]
        prev = by_quarter[prev_q]

        by_quarter[q]["qoq"] = {
            "completeness_delta": round(
                cur["completeness"]["overall_pct"] - prev["completeness"]["overall_pct"], 2
            ),
            "failure_rate_delta": round(
                cur["business_rules"]["failure_rate_pct"] - prev["business_rules"]["failure_rate_pct"], 4
            ),
            "avg_psi_delta": round(
                cur["drift"]["avg_psi"] - prev["drift"]["avg_psi"], 4
            ),
            "total_records_delta": cur["total_records"] - prev["total_records"],
            "total_records_pct": round(
                (cur["total_records"] - prev["total_records"]) / prev["total_records"] * 100, 2
            ) if prev["total_records"] > 0 else 0.0,
            "schema_quality_delta": round(
                cur["schema"]["quality_score"] - prev["schema"]["quality_score"], 2
            ),
        }
