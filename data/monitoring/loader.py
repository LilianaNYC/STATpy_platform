"""Source-data loading for the PD Performance Dash app.

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
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from ..analytics import constants as config
from ..common.text import normalize_model_name as _normalize_model_name

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
    """Load the portfolio Excel file, clean null sentinels, derive quarter labels."""
    log.info("Loading portfolio from %s [%s]", config.PORTFOLIO_FILE, config.PORTFOLIO_SHEET_NAME)

    df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=config.PORTFOLIO_SHEET_NAME)
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


def get_quarter_df(df: pd.DataFrame, quarter: str) -> pd.DataFrame:
    """Return rows for a specific quarter label."""
    return df[df["_quarter"] == quarter].copy()


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

    # -- mev_data (baseline scenario only): time series per model+MEV
    ts_df = pd.read_excel(
        xls,
        sheet_name=config.DUMMY_MEV_TIME_SERIES_SHEET_NAME,
    ).dropna(how="all")
    ts_df = ts_df[ts_df["Scenario"] == "baseline"].copy()
    ts_df["_quarter_label"] = ts_df["Date"].astype(str).map(_date_to_quarter_label)
    ts_df["MEV Value"] = pd.to_numeric(ts_df["MEV Value"], errors="coerce")
    ts_df = ts_df.dropna(subset=["MEV Value"])

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
            time_series = {
                row["_quarter_label"]: round(float(row["MEV Value"]), 6)
                for _, row in series_rows.iterrows()
            }
            dev_values = [
                v for q, v in time_series.items()
                if not dev_date or q <= dev_date
            ]
            display_name = mev_long_names.get(mev_name, mev_name)
            mevs[display_name] = {
                "dev_range": _compute_dev_range(dev_values, dev_date),
                "time_series": time_series,
            }

        contributions = {}
        raw_contribs = model_mev_contributions.get(model_key, {})
        for mnemonic, value in raw_contribs.items():
            display_name = mev_long_names.get(mnemonic, mnemonic)
            contributions[display_name] = value

        catalog[model_name] = {
            "segments": model_segments.get(model_key, []),
            "severe_scenario_date": "",
            "mevs": mevs,
            "contributions": contributions,
        }

    return catalog, mev_mnemonic_map, mev_description_map


# ---------------------------------------------------------------------------
# Rank-ordering facilities
# ---------------------------------------------------------------------------
def _clean_rank_ordering_series(raw_series: Any) -> dict[str, float]:
    if not isinstance(raw_series, dict):
        return {}
    clean: dict[str, float] = {}
    for raw_period, raw_value in raw_series.items():
        period = str(raw_period).strip()
        value = pd.to_numeric(raw_value, errors="coerce")
        if period and pd.notna(value):
            clean[period] = round(float(value), 6)
    return clean


def _clean_rank_ordering_forecast(raw_forecast: Any) -> dict[str, dict[str, float]]:
    if not isinstance(raw_forecast, dict):
        raw_forecast = {}
    return {
        "base": _clean_rank_ordering_series(raw_forecast.get("base", {})),
        "severe": _clean_rank_ordering_series(raw_forecast.get("severe", {})),
    }


def load_pd_rank_ordering_facilities() -> dict[str, Any]:
    """Load the dummy facility-level PD paths used by the scenario rank-ordering section.

    Port of ``_load_pd_rank_ordering_facilities``.
    """
    path = config.FACILITIES_DUMMY_DATA_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.warning("PD rank-ordering dummy data file not found: %s", path)
        return {}
    except json.JSONDecodeError as exc:
        log.warning("PD rank-ordering dummy data file could not be parsed: %s", exc)
        return {}

    if not isinstance(payload, dict):
        log.warning("PD rank-ordering dummy data must be a facility-keyed JSON object.")
        return {}

    facilities: dict[str, Any] = {}
    for raw_facility_id, raw_payload in payload.items():
        if not isinstance(raw_payload, dict):
            continue

        facility_id = str(raw_facility_id).strip()
        if not facility_id:
            continue

        facilities[facility_id] = {
            "segment": str(raw_payload.get("segment") or "").strip(),
            "pd_model": _normalize_model_name(raw_payload.get("pd_model")),
            "severe_scenario_date": str(raw_payload.get("severe_scenario_date") or ""),
            "acl_pd_historical": _clean_rank_ordering_series(raw_payload.get("acl_pd_historical", {})),
            "nco_pd_historical": _clean_rank_ordering_series(raw_payload.get("nco_pd_historical", {})),
            "acl_pd_forecast": _clean_rank_ordering_forecast(raw_payload.get("acl_pd_forecast", {})),
            "nco_pd_forecast": _clean_rank_ordering_forecast(raw_payload.get("nco_pd_forecast", {})),
        }

    return facilities


# ---------------------------------------------------------------------------
# Aggregated-sheet loader
# ---------------------------------------------------------------------------

PD_AGGREGATED_SHEET_NAME = "PD_Performance_Metrics"


def _build_observations_from_aggregated(agg_df: pd.DataFrame) -> tuple[dict, list[dict], list[str], list[dict]]:
    """Synthesize facility-level observations from the pre-aggregated metrics sheet.

    Returns ``(performance_horizons, performance_observations,
    rating_values, rating_migration_observations)``.

    For each model × quarter × horizon row in the aggregated data, two
    synthetic facility rows are created whose average observed/predicted
    values and EAD reproduce the aggregated metrics. The existing
    calculation pipeline processes these rows identically to real
    facility-level data.
    """
    performance_horizons = config.PD_HORIZON_COLUMNS

    obs_map: dict[tuple[str, str, str], dict] = {}

    for _, row in agg_df.iterrows():
        quarter = str(row["quarter"]).strip()
        model = _normalize_model_name(row.get("model"))
        segments = [s.strip() for s in str(row.get("segment", "")).split(",") if s.strip()]
        horizon = str(row.get("horizon", "")).strip()
        if not quarter or not model or not horizon or not segments:
            continue

        predicted = row.get("predicted_default_rate")
        observed_dr = row.get("observed_default_rate")
        ead = row.get("ead")
        n_segments = len(segments)

        for segment in segments:
            key = (quarter, model, segment)
            if key not in obs_map:
                obs_map[key] = {"quarter": quarter, "model": model, "segment": segment, "rating": "5", "horizons": {}}

            if pd.notna(predicted) and pd.notna(observed_dr):
                n = max(int(row.get("default_count_1y", 20) or 20), 2) if horizon == "1y" else 20
                n_defaults = max(1, round(observed_dr * n))
                n_non_defaults = max(1, n - n_defaults)
                total = n_defaults + n_non_defaults
                segment_ead = float(ead) / n_segments if pd.notna(ead) else None
                facility_ead = segment_ead / total if segment_ead is not None else None

                obs_map[key]["horizons"][horizon] = {
                    "observed_dr": float(observed_dr),
                    "predicted": float(predicted),
                    "ead": facility_ead,
                    "n_defaults": n_defaults,
                    "n_non_defaults": n_non_defaults,
                }

    observations = []
    for key, entry in obs_map.items():
        for horizon_key, h_data in entry["horizons"].items():
            for i in range(h_data["n_defaults"]):
                obs = {"quarter": entry["quarter"], "model": entry["model"],
                       "segment": entry["segment"], "rating": entry["rating"], "horizons": {}}
                obs["horizons"][horizon_key] = {
                    "observed": 1, "predicted": round(h_data["predicted"], 8),
                    "ead": round(h_data["ead"], 2) if h_data["ead"] else None,
                }
                observations.append(obs)
            for i in range(h_data["n_non_defaults"]):
                obs = {"quarter": entry["quarter"], "model": entry["model"],
                       "segment": entry["segment"], "rating": entry["rating"], "horizons": {}}
                obs["horizons"][horizon_key] = {
                    "observed": 0, "predicted": round(h_data["predicted"], 8),
                    "ead": round(h_data["ead"], 2) if h_data["ead"] else None,
                }
                observations.append(obs)

    return performance_horizons, observations, [], []


def load_pd_performance_data_from_aggregated() -> dict[str, Any]:
    """Load from the PD_Performance_Metrics sheet instead of facility-level data."""
    log.info("Loading PD aggregated metrics from %s [%s]", config.PORTFOLIO_FILE, PD_AGGREGATED_SHEET_NAME)

    agg_df = pd.read_excel(config.PORTFOLIO_FILE, sheet_name=PD_AGGREGATED_SHEET_NAME)
    agg_df = agg_df.dropna(how="all")

    quarters = sorted(agg_df["quarter"].dropna().unique())
    latest_quarter = quarters[-1] if quarters else ""
    previous_quarter = quarters[-2] if len(quarters) > 1 else ""

    model_names = sorted(agg_df["model"].dropna().map(_normalize_model_name).unique())
    segment_values = sorted({
        s.strip()
        for raw in agg_df["segment"].dropna().unique()
        for s in str(raw).split(",")
        if s.strip()
    })

    monitoring_thresholds = load_monitoring_thresholds()
    performance_horizons, performance_observations, rating_values, rating_migration_observations = (
        _build_observations_from_aggregated(agg_df)
    )
    mev_catalog, mev_mnemonic_map, mev_description_map = load_pd_mev_catalog()

    return {
        "portfolio": agg_df,
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
        "mev_catalog": mev_catalog,
        "mev_mnemonic_map": mev_mnemonic_map,
        "mev_description_map": mev_description_map,
        "rank_ordering_facilities": load_pd_rank_ordering_facilities(),
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
        "rank_ordering_facilities": load_pd_rank_ordering_facilities(),
    }
