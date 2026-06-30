"""Persistence / source-data loading for the PD Performance Dash app.

This is a trimmed port of ``data_manager.py`` and the data-layer helpers in
``callbacks/monitoring_pd_models_callbacks.py`` from the original monitoring
dashboard, keeping only what the PD Performance tab needs:

- the portfolio extract (with ``_quarter`` / ``_snapshot_date`` derived columns)
- the PD/CRR/RAG-assignment threshold tables
- row-level PD performance observations (1y / 2y / NCO 1y)
- worst-grade rating-migration observations
- the dummy MEV catalog and rank-ordering facility data

Functions ``_build_model_rows``, ``_build_model_quarter_breakdown``,
``_build_model_segment_quarter_breakdown`` and ``_build_threshold_summary``
from the original ``build_monitoring_pd_models`` are intentionally NOT
ported -- they feed the model-overview tables on other tabs and are not
referenced by ``renderPdModels()``'s live PD Performance sections. The model
and segment filter option lists are instead derived directly from the
portfolio dataframe.

Feature-private -- only :mod:`features.monitoring.services.data_service`
reads from this module (plus one cross-feature read from
:mod:`features.saas.repositories.loader` as a best-effort MEV catalog
fallback). The ``Filters`` sheet reader lives in ``data/filters/`` instead
-- see that package's docstring for why.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ....data.analytics import constants as config
from ....data.common.text import normalize_model_name as _normalize_model_name

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def _label(ts: pd.Timestamp) -> str:
    """Convert a quarter-end timestamp to a label like '2025Q1'."""
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}Q{q}"


# ---------------------------------------------------------------------------
# Portfolio loading
# ---------------------------------------------------------------------------
def load_portfolio() -> pd.DataFrame:
    """Load the portfolio Excel file, clean null sentinels, derive quarter labels.

    The facility-level ``Portfolio`` sheet is no longer used by the PD
    Performance tab (its metrics are read directly from
    ``PD_Performance_Metrics``). If the sheet is absent, return an empty frame
    so the app still loads.
    """
    log.info("Loading portfolio from %s [%s]", config.PORTFOLIO_FILE, config.PORTFOLIO_SHEET_NAME)

    try:
        df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=config.PORTFOLIO_SHEET_NAME)
    except (ValueError, KeyError):
        log.info("Portfolio sheet '%s' not found; using empty portfolio.", config.PORTFOLIO_SHEET_NAME)
        return pd.DataFrame(columns=[config.DATE_COLUMN, "_quarter", "_snapshot_date"])

    df.replace(config.NULL_SENTINELS, pd.NA, inplace=True)

    df[config.DATE_COLUMN] = pd.to_datetime(df[config.DATE_COLUMN])
    df["_quarter"] = df[config.DATE_COLUMN].apply(_label)
    df["_snapshot_date"] = df[config.DATE_COLUMN].dt.date

    log.info("Loaded %d records across %d quarters", len(df), df["_quarter"].nunique())
    return df


def get_quarters(df: pd.DataFrame) -> list[str]:
    """Return sorted list of all available quarter labels."""
    dates = df[config.DATE_COLUMN].sort_values().unique()
    labels = [_label(pd.Timestamp(d)) for d in dates]
    return sorted(set(labels))


def get_snapshot_date(df: pd.DataFrame, quarter: str) -> str:
    """Return the snapshot date string for a quarter."""
    rows = df[df["_quarter"] == quarter]
    if rows.empty:
        return ""
    return str(rows["_snapshot_date"].iloc[0])


def get_model_names(df: pd.DataFrame) -> list[str]:
    values = df[config.PD_MODEL_COLUMN].map(_normalize_model_name)
    return sorted({value for value in values if value})


def get_segment_values(df: pd.DataFrame) -> list[str]:
    values = df[config.SEGMENT_COLUMN].astype(str).str.strip()
    return sorted({value for value in values if value and value.lower() != "nan"})


# ---------------------------------------------------------------------------
# Monitoring thresholds
# ---------------------------------------------------------------------------
def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to a list of JSON-safe records (NaN -> None)."""
    if df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict(orient="records")


def load_monitoring_thresholds() -> dict[str, list[dict[str, Any]]]:
    """Load the PD / CRR-master-scale / RAG-assignment sheets.

    The original ``load_monitoring_thresholds`` only loads sheets whose
    config key ends with ``_thresholds_sheet_name`` or equals
    ``crr_master_scale_sheet_name`` -- which means ``RAG_Assignment_PD`` is
    never loaded by the existing pipeline. We load all three sheets the PD
    Performance tab needs explicitly here.
    """
    thresholds: dict[str, list[dict[str, Any]]] = {}

    for key, sheet_name in (
        ("pd_thresholds", config.PD_THRESHOLDS_SHEET_NAME),
        ("crr_master_scale", config.CRR_MASTER_SCALE_SHEET_NAME),
        ("rag_assignment_pd", config.RAG_ASSIGNMENT_PD_SHEET_NAME),
        ("lgd_thresholds", config.LGD_THRESHOLDS_SHEET_NAME),
        ("loss_thresholds", config.LOSS_THRESHOLDS_SHEET_NAME),
        ("scenario_test_thresholds", "Scenario_Test_Thresholds"),
    ):
        try:
            df = pd.read_excel(config.MONITORING_THRESHOLDS_FILE, sheet_name=sheet_name)
            thresholds[key] = _records(df)
            log.info("Loaded thresholds sheet '%s' as %s (%d rows)", sheet_name, key, len(df))
        except Exception as exc:  # noqa: BLE001 - mirror original best-effort loading
            log.warning("Unable to load sheet '%s' for %s: %s", sheet_name, key, exc)
            thresholds[key] = []

    return thresholds


# ---------------------------------------------------------------------------
# PD performance observations (1y / 2y / NCO 1y)
# ---------------------------------------------------------------------------
def build_pd_performance_observations(df: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the compact row-level payload needed for interactive PD metrics.

    Port of ``_build_pd_performance_observations``.
    """
    model_column = config.PD_MODEL_COLUMN
    segment_column = config.SEGMENT_COLUMN
    rating_column = config.RATING_COLUMN
    horizon_columns = config.PD_HORIZON_COLUMNS

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


# ---------------------------------------------------------------------------
# Rating migration (worst-grade per facility per quarter)
# ---------------------------------------------------------------------------
def build_rating_migration_observations(df: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
    """Return one worst-grade rating row per facility and quarter.

    Port of ``_build_rating_migration_observations``.
    """
    model_column = config.PD_MODEL_COLUMN
    segment_column = config.SEGMENT_COLUMN
    id_column = config.FACILITY_ID_COLUMN
    rating_column = config.RATING_COLUMN

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


# ---------------------------------------------------------------------------
# MEV catalog
# ---------------------------------------------------------------------------
def _date_to_quarter_label(date_str: str) -> str:
    """Convert ``'MM/DD/YYYY'`` or a pandas Timestamp to ``'YYYY-QN'``."""
    ts = pd.Timestamp(date_str)
    return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"


def _compute_dev_range(
    values: list[float], development_date: str,
) -> dict[str, Any]:
    """Compute development-period statistics from *values* (all baseline
    observations up to and including *development_date*).
    """
    if not values:
        return {
            "min": None, "max": None, "mean": None,
            "2std_lower": None, "2std_upper": None,
            "development_date": development_date,
        }
    arr = np.array(values, dtype=float)
    mean = round(float(np.mean(arr)), 6)
    std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    return {
        "min": round(float(np.min(arr)), 6),
        "max": round(float(np.max(arr)), 6),
        "mean": mean,
        "2std_lower": round(mean - 2 * std, 6),
        "2std_upper": round(mean + 2 * std, 6),
        "development_date": development_date,
    }


def load_pd_mev_catalog() -> dict[str, Any]:
    """Load the MEV catalog from ``dummy_mev_data.xlsx``.

    Reads the model characteristics, transformed MEV descriptions, and
    baseline time-series data from the Excel workbook. Development-range
    statistics (``dev_range``) are computed from baseline observations up
    to each model's development date.
    """
    path = config.DUMMY_MEV_DATA_FILE
    try:
        xls = pd.ExcelFile(path)
    except FileNotFoundError:
        log.warning("MEV workbook not found: %s", path)
        return {}

    # -- model_characteristic: development dates, segments, descriptive names
    mc_df = pd.read_excel(
        xls,
        sheet_name=config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
    ).dropna(how="all")

    dev_dates: dict[str, str] = {}
    descriptive_names: dict[str, str] = {}
    model_types: dict[str, str] = {}
    for _, row in mc_df.iterrows():
        model_key = str(row.get("Model Name", "")).strip()
        if not model_key:
            continue
        date_val = row.get("Development date", "")
        if date_val:
            dev_dates[model_key] = _date_to_quarter_label(str(date_val))
        desc = row.get("Model descriptive name", "")
        if desc:
            descriptive_names[model_key] = str(desc).strip()
        model_type = str(row.get("Model Type", "")).strip().upper()
        if model_type:
            model_types[model_key] = model_type

    # -- transformed_mevs_description: model→segment and model→MEV mapping
    desc_df = pd.read_excel(
        xls,
        sheet_name=config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
    ).dropna(how="all")

    model_segments: dict[str, list[str]] = {}
    mev_long_names: dict[str, str] = {}
    mev_descriptions: dict[str, str] = {}
    model_transformed_mevs: dict[str, set[str]] = {}
    model_mev_contributions: dict[str, dict[str, float]] = {}
    for _, row in desc_df.iterrows():
        model_key = str(row.get("Model Name", "")).strip()
        segment = str(row.get("Segment", "")).strip()
        mnemonic = str(row.get("US Mnemonic", "")).strip()
        long_name = str(row.get("Long Name", "")).strip()
        description = str(row.get("Description", "")).strip()
        contribution = row.get("Model controbution", row.get("Model contribution"))
        if model_key and segment:
            model_segments.setdefault(model_key, [])
            if segment not in model_segments[model_key]:
                model_segments[model_key].append(segment)
        if mnemonic and long_name:
            mev_long_names[mnemonic] = long_name
        if mnemonic and description:
            mev_descriptions[mnemonic] = description
        if model_key and mnemonic:
            model_transformed_mevs.setdefault(model_key, set()).add(mnemonic)
        if model_key and mnemonic and contribution is not None:
            try:
                model_mev_contributions.setdefault(model_key, {})[mnemonic] = float(contribution)
            except (TypeError, ValueError):
                pass

    # -- mev_data (all scenarios): time series per model+MEV+scenario
    ts_df = pd.read_excel(
        xls,
        sheet_name=config.DUMMY_MEV_TIME_SERIES_SHEET_NAME,
    ).dropna(how="all")
    ts_df["Date"] = pd.to_datetime(ts_df["Date"], errors="coerce")
    ts_df["Quarter"] = pd.to_numeric(ts_df.get("Quarter"), errors="coerce")
    ts_df["Run For"] = ts_df.get("Run For").map(lambda value: str(value).strip() if value is not None else "")
    ts_df["Scenario"] = ts_df.get("Scenario").map(lambda value: str(value).strip() if value is not None else "")
    ts_df["_quarter_label"] = ts_df["Date"].astype(str).map(_date_to_quarter_label)
    ts_df["MEV Value"] = pd.to_numeric(ts_df["MEV Value"], errors="coerce")
    ts_df = ts_df.dropna(subset=["Date", "MEV Value"])

    xls.close()

    # -- assemble the catalog keyed by descriptive model name
    all_model_keys = sorted(
        set(ts_df["Model Name"].dropna().unique())
        | set(desc_df["Model Name"].dropna().unique()),
    )

    mev_mnemonic_map: dict[str, str] = {
        long_name: mnemonic for mnemonic, long_name in mev_long_names.items()
    }
    mev_description_map: dict[str, str] = {
        mev_long_names.get(mnemonic, mnemonic): desc
        for mnemonic, desc in mev_descriptions.items()
        if mnemonic in mev_long_names
    }

    catalog: dict[str, Any] = {}
    for model_key in all_model_keys:
        model_name = _normalize_model_name(
            descriptive_names.get(model_key, model_key),
        )
        if not model_name:
            continue

        model_ts = ts_df[ts_df["Model Name"] == model_key]
        allowed = model_transformed_mevs.get(model_key, set())
        mev_names_for_model = sorted(
            name for name in model_ts["MEV Name"].unique() if name in allowed
        )
        dev_date = dev_dates.get(model_key, "")

        mevs: dict[str, Any] = {}
        for mev_name in mev_names_for_model:
            series_rows = model_ts[model_ts["MEV Name"] == mev_name].sort_values("_quarter_label")
            baseline_rows = series_rows[series_rows["Scenario"] == "baseline"]
            time_series = {
                row["_quarter_label"]: round(float(row["MEV Value"]), 6)
                for _, row in baseline_rows.iterrows()
            }
            scenario_series: dict[str, dict[str, float]] = {}
            for scenario in series_rows["Scenario"].dropna().unique():
                sc_rows = series_rows[series_rows["Scenario"] == scenario]
                scenario_series[str(scenario).strip()] = {
                    row["_quarter_label"]: round(float(row["MEV Value"]), 6)
                    for _, row in sc_rows.iterrows()
                }
            scenario_series_by_cycle: dict[str, dict[str, dict[str, float]]] = {}
            scenario_quarter_zero_by_cycle: dict[str, dict[str, str]] = {}
            for run_for in series_rows["Run For"].dropna().unique():
                cycle_rows = series_rows[series_rows["Run For"] == run_for]
                cycle_key = str(run_for).strip()
                if not cycle_key:
                    continue
                for scenario in cycle_rows["Scenario"].dropna().unique():
                    scenario_key = str(scenario).strip()
                    sc_rows = cycle_rows[cycle_rows["Scenario"] == scenario]
                    scenario_series_by_cycle.setdefault(cycle_key, {})[scenario_key] = {
                        row["_quarter_label"]: round(float(row["MEV Value"]), 6)
                        for _, row in sc_rows.iterrows()
                    }
                    q0_rows = sc_rows[sc_rows["Quarter"] == 0].sort_values("Date")
                    if not q0_rows.empty:
                        scenario_quarter_zero_by_cycle.setdefault(cycle_key, {})[scenario_key] = q0_rows.iloc[0]["_quarter_label"]
            dev_values = [
                v for q, v in time_series.items()
                if not dev_date or q <= dev_date
            ]
            display_name = mev_long_names.get(mev_name, mev_name)
            mevs[display_name] = {
                "dev_range": _compute_dev_range(dev_values, dev_date),
                "time_series": time_series,
                "scenario_series": scenario_series,
                "scenario_series_by_cycle": scenario_series_by_cycle,
                "scenario_quarter_zero_by_cycle": scenario_quarter_zero_by_cycle,
            }

        contributions = {}
        raw_contribs = model_mev_contributions.get(model_key, {})
        for mnemonic, value in raw_contribs.items():
            display_name = mev_long_names.get(mnemonic, mnemonic)
            contributions[display_name] = value

        catalog[model_name] = {
            "model_type": model_types.get(model_key, ""),
            "segments": model_segments.get(model_key, []),
            "severe_scenario_date": "",
            "mevs": mevs,
            "contributions": contributions,
        }

    return catalog, mev_mnemonic_map, mev_description_map


# ---------------------------------------------------------------------------
# Aggregated-sheet loader
# ---------------------------------------------------------------------------

PD_AGGREGATED_SHEET_NAME = "PD_Performance_Metrics"
LGD_AGGREGATED_SHEET_NAME = "LGD_Performance_Metrics"
EAD_AGGREGATED_SHEET_NAME = "EAD_Performance_Metrics"
LOSS_AGGREGATED_SHEET_NAME = "Loss_Performance_Metrics"
PD_SENSITIVITY_SHEET_NAME = "PD_Sensitivity_Projections"

# Sheet column -> metric-row key consumed by each performance page/data module.
_LGD_METRIC_COLUMN_MAP = {
    "me": "ME",
    "rmse": "RMSE",
    "kendall_tau": "Kendall's Tau",
    "predicted_lgd": "Predicted LGD",
    "actual_lgd": "Actual LGD",
    "recovery_rate": "Recovery Rate",
    "observations": "Observations",
    "defaults": "Defaults",
}
_EAD_METRIC_COLUMN_MAP = {
    "me": "ME",
    "rmse": "RMSE",
    "kendall_tau": "Kendall's Tau",
    "predicted_ead": "Predicted EAD",
    "actual_ead": "Actual EAD",
    "observations": "Observations",
    "defaults": "Defaults",
}
_LOSS_METRIC_COLUMN_MAP = {
    "me": "ME",
    "me_pct": "ME %",
    "predicted_loss": "Predicted Loss",
    "actual_loss": "Actual Loss",
    "defaults": "Defaults",
    "balance": "Balance",
    "observations": "Observations",
}


def _build_metric_rows_store(sheet_name: str, column_map: dict[str, str]) -> dict[str, Any]:
    """Load a precomputed performance sheet into a per-cycle metric-row store.

    Returns ``{cycle: {"quarters": [...], "metrics_store": {(level, value): [rows]}}}``
    where each row matches the metric-row shape the matching page expects.
    Values are taken verbatim from the sheet — no metric is recomputed.
    """
    try:
        df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=sheet_name)
    except (FileNotFoundError, ValueError, KeyError):
        return {}
    df = df.dropna(how="all")
    if df.empty or "reporting_cycle" not in df.columns:
        return {}

    def _num(value):
        return float(value) if pd.notna(value) else None

    by_cycle: dict[str, Any] = {}
    for cycle in sorted(df["reporting_cycle"].dropna().unique()):
        cycle_df = df[df["reporting_cycle"] == cycle]
        store: dict = {}
        for _, row in cycle_df.iterrows():
            level = str(row.get("level", "")).strip().lower()
            value = str(row.get("model_or_segment", "")).strip()
            quarter = str(row.get("quarter", "")).strip()
            if not level or not value or not quarter:
                continue
            metric_row = {"Monitoring Period": quarter}
            for col, key in column_map.items():
                metric_row[key] = _num(row.get(col)) if col in cycle_df.columns else None
            for count_key in ("Observations", "Defaults"):
                if metric_row.get(count_key) is not None:
                    metric_row[count_key] = int(metric_row[count_key])
            store.setdefault((level, value), []).append(metric_row)
        for key in store:
            store[key].sort(key=lambda r: r["Monitoring Period"])
        quarters = sorted(cycle_df["quarter"].dropna().astype(str).unique())
        by_cycle[cycle] = {"quarters": quarters, "metrics_store": store}
    return by_cycle


def load_lgd_performance_metrics() -> dict[str, Any]:
    """Load LGD metrics per reporting cycle from ``LGD_Performance_Metrics``."""
    return _build_metric_rows_store(LGD_AGGREGATED_SHEET_NAME, _LGD_METRIC_COLUMN_MAP)


def load_ead_performance_metrics() -> dict[str, Any]:
    """Load EAD metrics per reporting cycle from ``EAD_Performance_Metrics``."""
    return _build_metric_rows_store(EAD_AGGREGATED_SHEET_NAME, _EAD_METRIC_COLUMN_MAP)


def load_loss_performance_metrics() -> dict[str, Any]:
    """Load Loss metrics per reporting cycle from ``Loss_Performance_Metrics``."""
    return _build_metric_rows_store(LOSS_AGGREGATED_SHEET_NAME, _LOSS_METRIC_COLUMN_MAP)


def load_pd_sensitivity_projections() -> list[dict[str, Any]]:
    """Load projected PD sensitivity rows from ``PD_Sensitivity_Projections``."""
    try:
        df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=PD_SENSITIVITY_SHEET_NAME)
    except (FileNotFoundError, ValueError, KeyError):
        return []

    df = df.dropna(how="all")
    required = {
        "reporting_cycle",
        "level",
        "model_or_segment",
        "projection_quarter",
        "scenario_variant",
        "projected_pd",
    }
    if "quarter" not in df.columns and "projection_offset" in df.columns:
        df = df.rename(columns={"projection_offset": "quarter"})
    required.add("quarter")
    if df.empty or not required.issubset(df.columns):
        return []

    df = df.copy()
    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce")
    df["projection_quarter"] = pd.to_datetime(df["projection_quarter"], errors="coerce")
    df["projected_pd"] = pd.to_numeric(df["projected_pd"], errors="coerce")
    df = df.dropna(subset=["quarter", "projection_quarter", "projected_pd"])

    # MM_P0 / MM_Pm are scenario-independent margins read verbatim from the
    # sheet: MM_P0 is a single value per entity, MM_Pm varies by projection
    # quarter. Both repeat across the scenario rows.
    def _opt_num(row, column):
        if column not in df.columns or pd.isna(row.get(column)):
            return None
        return round(float(row[column]), 8)

    records = []
    for _, row in df.iterrows():
        records.append({
            "reporting_cycle": str(row["reporting_cycle"]).strip(),
            "level": str(row["level"]).strip().lower(),
            "model_or_segment": str(row["model_or_segment"]).strip(),
            "quarter": int(row["quarter"]),
            "projection_quarter": row["projection_quarter"].date().isoformat(),
            "scenario_variant": str(row["scenario_variant"]).strip(),
            "base_scenario": str(row.get("base_scenario") or "").strip(),
            "shock_std": float(row["shock_std"]) if "shock_std" in df.columns and pd.notna(row.get("shock_std")) else None,
            "shock_direction": str(row.get("shock_direction") or "").strip(),
            "projected_pd": round(float(row["projected_pd"]), 8),
            "mm_p0": _opt_num(row, "MM_P0"),
            "mm_pm": _opt_num(row, "MM_Pm"),
        })

    return records


def _build_observations_from_aggregated(agg_df: pd.DataFrame) -> tuple[dict, list[dict], list[str], list[dict]]:
    """Deprecated facility synthesis.

    PD Performance metrics are now read verbatim from the
    ``PD_Performance_Metrics`` tab via :func:`_build_metrics_store`; no
    facility-level data is synthesized or recomputed. Retained as a no-op so
    existing call sites keep working.
    """
    return config.PD_HORIZON_COLUMNS, [], [], []


# Metric columns read verbatim from the PD_Performance_Metrics tab.
_PD_METRIC_COLUMNS = (
    "confidence_interval_test",
    "notching_test_signed",
    "notching_test_abs",
    "observed_default_rate",
    "predicted_default_rate",
    "actual_expected_ratio",
    "accuracy_ratio",
    "go_live_accuracy_ratio",
    "delta_accuracy_ratio",
    "gini_coefficient",
    "ks_statistic",
    "kendall_tau",
    "brier_score",
    "population_stability_index",
    "rating_migration_index",
    "ead",
    "ead_share",
    "default_count_1y",
)

# The horizons each per-horizon row is replicated to when its ``horizon`` cell
# is left blank (i.e. the metric is horizon-agnostic, e.g. discrimination).
_PD_HORIZONS = ("1y", "2y", "nco_1y")


def _build_metrics_store(cycle_df: pd.DataFrame) -> dict:
    """Build the precomputed-metrics lookup the calculation engine reads from.

    The ``PD_Performance_Metrics`` tab is keyed by ``reporting_cycle × level ×
    quarter × model_or_segment × horizon``. The store is keyed by
    ``(level, model_or_segment, quarter, horizon)`` and every value is taken
    verbatim from the sheet. Rows whose ``horizon`` is blank carry
    horizon-agnostic metrics (discrimination, PSI, rating migration); they are
    merged into every horizon for that ``(level, value, quarter)`` so the engine
    finds them regardless of which horizon it queries.
    """
    go_live_quarter = config.PD_GO_LIVE_QUARTER_END

    def _num(value):
        return float(value) if pd.notna(value) else None

    # Collect, per (level, value, quarter), the blank-horizon agnostic metrics
    # and each specific horizon's metrics.
    grouped: dict = {}
    for _, row in cycle_df.iterrows():
        quarter = str(row["quarter"]).strip()
        level = str(row.get("level", "")).strip().lower()
        value = str(row.get("model_or_segment", row.get("model", "") or row.get("segment", ""))).strip()
        horizon = str(row.get("horizon", "")).strip()
        if not quarter or not level or not value:
            continue
        metrics = {col: _num(row.get(col)) for col in _PD_METRIC_COLUMNS if col in cycle_df.columns}
        bucket = grouped.setdefault((level, value, quarter), {"shared": {}, "horizons": {}})
        if horizon in ("", "nan", "all"):
            bucket["shared"].update({k: v for k, v in metrics.items() if v is not None})
        else:
            bucket["horizons"][horizon] = metrics

    store: dict = {}
    for (level, value, quarter), bucket in grouped.items():
        shared = bucket["shared"]
        horizons = bucket["horizons"] or {h: {} for h in _PD_HORIZONS}
        for horizon, specific in horizons.items():
            merged = {**shared, **{k: v for k, v in specific.items() if v is not None}}
            merged.setdefault("go_live_quarter", go_live_quarter)
            store[(level, value, quarter, horizon)] = merged

    return store


def load_pd_performance_data_from_aggregated() -> dict[str, Any]:
    """Load from the PD_Performance_Metrics sheet instead of facility-level data."""
    log.info("Loading PD aggregated metrics from %s [%s]", config.PORTFOLIO_FILE, PD_AGGREGATED_SHEET_NAME)

    agg_df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=PD_AGGREGATED_SHEET_NAME)
    agg_df = agg_df.dropna(how="all")

    portfolio = load_portfolio()

    quarters = sorted(agg_df["quarter"].dropna().unique())
    latest_quarter = quarters[-1] if quarters else ""
    previous_quarter = quarters[-2] if len(quarters) > 1 else ""

    # Models/segments are the entities under each ``level`` in the sheet. The
    # "All Models" portfolio entity is the implicit default, not a pickable model.
    is_model = agg_df["level"].astype(str).str.lower() == "model"
    is_segment = agg_df["level"].astype(str).str.lower() == "segment"
    data_model_names = sorted({
        m for m in agg_df.loc[is_model, "model_or_segment"].dropna().map(_normalize_model_name).unique()
        if m and m != "All Models"
    })
    data_segment_values = sorted(agg_df.loc[is_segment, "model_or_segment"].dropna().astype(str).str.strip().unique())
    model_names = data_model_names or ["PD Model A", "PD Model B"]
    segment_values = data_segment_values or ["Cyclical", "Defensive", "O&M", "LoL", "IVB"]

    monitoring_thresholds = load_monitoring_thresholds()

    # Build observations per reporting cycle
    reporting_cycles = sorted(agg_df["reporting_cycle"].dropna().unique()) if "reporting_cycle" in agg_df.columns else []
    observations_by_cycle = {}
    for cycle in reporting_cycles:
        cycle_df = agg_df[agg_df["reporting_cycle"] == cycle]
        obs = _build_observations_from_aggregated(cycle_df)
        cycle_quarters = sorted(cycle_df["quarter"].dropna().unique())
        observations_by_cycle[cycle] = {
            "performance_horizons": obs[0],
            "performance_observations": obs[1],
            "rating_values": obs[2],
            "rating_migration_observations": obs[3],
            "quarters": cycle_quarters,
            "metrics_store": _build_metrics_store(cycle_df),
        }

    # Default to first available cycle for backwards compatibility
    default_cycle = reporting_cycles[0] if reporting_cycles else None
    if default_cycle and default_cycle in observations_by_cycle:
        default_obs = observations_by_cycle[default_cycle]
        performance_horizons = default_obs["performance_horizons"]
        performance_observations = default_obs["performance_observations"]
        rating_values = default_obs["rating_values"]
        rating_migration_observations = default_obs["rating_migration_observations"]
    else:
        performance_horizons, performance_observations, rating_values, rating_migration_observations = (
            _build_observations_from_aggregated(agg_df)
        )

    mev_catalog, mev_mnemonic_map, mev_description_map = load_pd_mev_catalog()

    return {
        "portfolio": portfolio,
        "quarters": quarters,
        "latest_quarter": latest_quarter,
        "previous_quarter": previous_quarter,
        "latest_snapshot_date": latest_quarter,
        "previous_snapshot_date": previous_quarter,
        "source_file": config.PORTFOLIO_FILE.name,
        "model_names": model_names,
        "segment_values": segment_values,
        "monitoring_thresholds": monitoring_thresholds,
        "performance_horizons": performance_horizons,
        "performance_observations": performance_observations,
        "rating_values": rating_values,
        "rating_migration_observations": rating_migration_observations,
        "observations_by_cycle": observations_by_cycle,
        "reporting_cycles": reporting_cycles,
        "mev_catalog": mev_catalog,
        "mev_mnemonic_map": mev_mnemonic_map,
        "mev_description_map": mev_description_map,
        "sensitivity_projections": load_pd_sensitivity_projections(),
        "rank_ordering_facilities": {},
        "lgd_observations_by_cycle": load_lgd_performance_metrics(),
        "ead_observations_by_cycle": load_ead_performance_metrics(),
        "loss_observations_by_cycle": load_loss_performance_metrics(),
    }


# ---------------------------------------------------------------------------
# Top-level loader
# ---------------------------------------------------------------------------
def load_pd_performance_data() -> dict[str, Any]:
    """Load and assemble everything the PD Performance tab needs."""
    portfolio = load_portfolio()
    quarters = get_quarters(portfolio)
    latest_quarter = quarters[-1] if quarters else ""
    previous_quarter = quarters[-2] if len(quarters) > 1 else ""
    monitoring_thresholds = load_monitoring_thresholds()
    performance_horizons, performance_observations = build_pd_performance_observations(portfolio)
    rating_values, rating_migration_observations = build_rating_migration_observations(portfolio)
    mev_catalog, mev_mnemonic_map, mev_description_map = load_pd_mev_catalog()

    return {
        "portfolio": portfolio,
        "quarters": quarters,
        "latest_quarter": latest_quarter,
        "previous_quarter": previous_quarter,
        "latest_snapshot_date": get_snapshot_date(portfolio, latest_quarter),
        "previous_snapshot_date": get_snapshot_date(portfolio, previous_quarter) if previous_quarter else "",
        "source_file": config.PORTFOLIO_FILE.name,
        "model_names": get_model_names(portfolio),
        "segment_values": get_segment_values(portfolio),
        "monitoring_thresholds": monitoring_thresholds,
        "performance_horizons": performance_horizons,
        "performance_observations": performance_observations,
        "rating_values": rating_values,
        "rating_migration_observations": rating_migration_observations,
        "mev_catalog": mev_catalog,
        "mev_mnemonic_map": mev_mnemonic_map,
        "mev_description_map": mev_description_map,
        "sensitivity_projections": load_pd_sensitivity_projections(),
        "rank_ordering_facilities": {},
        "lgd_observations_by_cycle": load_lgd_performance_metrics(),
        "ead_observations_by_cycle": load_ead_performance_metrics(),
        "loss_observations_by_cycle": load_loss_performance_metrics(),
    }
