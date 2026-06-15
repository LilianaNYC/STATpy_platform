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

from .. import monitoring_config as config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def _label(ts: pd.Timestamp) -> str:
    """Convert a quarter-end timestamp to a label like '2025Q1'."""
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}Q{q}"


def _normalize_model_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _ordered_unique_strings(values) -> list[str]:
    ordered_values: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip() if raw_value is not None and not pd.isna(raw_value) else ""
        if not value or value in seen:
            continue
        seen.add(value)
        ordered_values.append(value)
    return ordered_values


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
def load_pd_mev_catalog() -> dict[str, Any]:
    """Load the dummy MEV time-series catalog used by the PD MEV range section.

    Port of ``_load_pd_mev_catalog``.
    """
    path = config.MEV_DUMMY_DATA_FILE
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


def load_saas_model_names() -> list[str]:
    """Load SAAS model-name filter options from the dummy MEV workbook."""
    try:
        df = pd.read_excel(
            config.DUMMY_MEV_DATA_FILE,
            sheet_name=config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
            usecols=[config.DUMMY_MEV_MODEL_NAME_COLUMN],
        )
        model_names: list[str] = []
        seen: set[str] = set()
        for raw_value in df[config.DUMMY_MEV_MODEL_NAME_COLUMN].tolist():
            model_name = _normalize_model_name(raw_value)
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            model_names.append(model_name)

        if model_names:
            return model_names
        log.warning(
            "No SAAS model names found in %s [%s]; falling back to MEV catalog keys.",
            config.DUMMY_MEV_DATA_FILE,
            config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort loading keeps the page available
        log.warning(
            "Unable to load SAAS model names from %s [%s]: %s",
            config.DUMMY_MEV_DATA_FILE,
            config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
            exc,
        )

    return list(load_pd_mev_catalog().keys())


def load_saas_mev_workbook_data() -> dict[str, Any]:
    """Load the SAAS workbook data used by the top filters and MEV chart."""
    empty_time_series = pd.DataFrame(
        columns=["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value", "Model Name"]
    )
    empty_payload = {
        "model_names": load_saas_model_names(),
        "model_segments": {},
        "model_development_dates": {},
        "run_for_quarter_zero_dates": {},
        "model_mev_family_map": {},
        "segment_values": [],
        "run_for_values": [],
        "mev_label_map": {},
        "mev_group_label_map": {},
        "mev_description_map": {},
        "mev_time_series": empty_time_series,
    }

    try:
        transformed_df = pd.read_excel(
            config.DUMMY_MEV_DATA_FILE,
            sheet_name=config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
        )
        raw_df = pd.read_excel(
            config.DUMMY_MEV_DATA_FILE,
            sheet_name=config.DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME,
        )
        time_series_df = pd.read_excel(
            config.DUMMY_MEV_DATA_FILE,
            sheet_name=config.DUMMY_MEV_TIME_SERIES_SHEET_NAME,
        )
        model_characteristic_df = pd.read_excel(
            config.DUMMY_MEV_DATA_FILE,
            sheet_name=config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - keep the page available if workbook loading fails
        log.warning("Unable to load SAAS MEV workbook data from %s: %s", config.DUMMY_MEV_DATA_FILE, exc)
        return empty_payload

    transformed_df = transformed_df.where(pd.notna(transformed_df), None)
    raw_df = raw_df.where(pd.notna(raw_df), None)
    time_series_df = time_series_df.where(pd.notna(time_series_df), None)
    model_characteristic_df = model_characteristic_df.where(pd.notna(model_characteristic_df), None)

    model_segments: dict[str, str] = {}
    model_mev_map: dict[str, dict[str, set[str]]] = {}
    model_mev_family_map: dict[str, dict[str, list[str]]] = {}
    for row in transformed_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get(config.DUMMY_MEV_MODEL_NAME_COLUMN))
        segment = str(row.get("Segment") or "").strip()
        transformed_mev_name = str(row.get("US Mnemonic") or "").strip()
        raw_mev_names = [
            item.strip()
            for item in str(row.get("SAAS_raw_mnemonic") or "").split(",")
            if item.strip()
        ]
        if model_name and segment and model_name not in model_segments:
            model_segments[model_name] = segment
        if model_name:
            model_mev_map.setdefault(
                model_name,
                {"transformed": set(), "raw": set()},
            )
            if transformed_mev_name:
                model_mev_map[model_name]["transformed"].add(transformed_mev_name)
                model_mev_family_map.setdefault(model_name, {})
                if transformed_mev_name not in model_mev_family_map[model_name]:
                    model_mev_family_map[model_name][transformed_mev_name] = list(dict.fromkeys(raw_mev_names))
            if raw_mev_names:
                model_mev_map[model_name]["raw"].update(raw_mev_names)

    mev_label_map: dict[str, str] = {}
    mev_group_label_map: dict[str, str] = {}
    mev_description_map: dict[str, str] = {}
    for description_df in (transformed_df, raw_df):
        for row in description_df.to_dict(orient="records"):
            mev_name = str(row.get("US Mnemonic") or "").strip()
            long_name = str(row.get("Long Name") or "").strip()
            description = str(row.get("Description") or "").strip()
            if mev_name and long_name and mev_name not in mev_label_map:
                mev_label_map[mev_name] = long_name
            if mev_name and description and mev_name not in mev_description_map:
                mev_description_map[mev_name] = description
    for row in raw_df.to_dict(orient="records"):
        mev_name = str(row.get("US Mnemonic") or "").strip()
        group_mnemonic = str(row.get("Group Mnemonic") or "").strip()
        if mev_name and group_mnemonic and mev_name not in mev_group_label_map:
            mev_group_label_map[mev_name] = group_mnemonic

    time_series_df["Date"] = pd.to_datetime(time_series_df.get("Date"), dayfirst=False, errors="coerce")
    time_series_df["Quarter"] = pd.to_numeric(time_series_df.get("Quarter"), errors="coerce")
    time_series_df["Run For"] = time_series_df.get("Run For").map(lambda value: str(value).strip() if value is not None else "")
    time_series_df["Scenario"] = time_series_df.get("Scenario").map(lambda value: str(value).strip() if value is not None else "")
    time_series_df["MEV Name"] = time_series_df.get("MEV Name").map(lambda value: str(value).strip() if value is not None else "")
    time_series_df["Model Name"] = time_series_df.get("Model Name").map(_normalize_model_name)
    time_series_df["MEV Value"] = pd.to_numeric(time_series_df.get("MEV Value"), errors="coerce")
    time_series_df = time_series_df.dropna(subset=["Date", "MEV Value"])
    time_series_df = time_series_df[
        time_series_df["MEV Name"].astype(bool) & time_series_df["Model Name"].astype(bool)
    ][["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value", "Model Name"]].copy()

    run_for_quarter_zero_dates: dict[str, Any] = {}
    quarter_zero_df = time_series_df[time_series_df["Quarter"] == 0]
    for row in quarter_zero_df.to_dict(orient="records"):
        run_for = str(row.get("Run For") or "").strip()
        date_value = row.get("Date")
        if not run_for or date_value is None:
            continue
        if run_for not in run_for_quarter_zero_dates or date_value < run_for_quarter_zero_dates[run_for]:
            run_for_quarter_zero_dates[run_for] = date_value

    model_characteristic_df["Run For"] = model_characteristic_df.get("Run For").map(
        lambda value: str(value).strip() if value is not None else ""
    )
    model_characteristic_df["Model Name"] = model_characteristic_df.get(config.DUMMY_MEV_MODEL_NAME_COLUMN).map(
        _normalize_model_name
    )
    model_characteristic_df["Development date"] = pd.to_datetime(
        model_characteristic_df.get("Development date"),
        dayfirst=False,
        errors="coerce",
    )
    model_characteristic_df = model_characteristic_df.dropna(subset=["Development date"])
    model_development_dates: dict[str, dict[str, Any]] = {}
    for row in model_characteristic_df.to_dict(orient="records"):
        run_for = str(row.get("Run For") or "").strip()
        model_name = _normalize_model_name(row.get("Model Name"))
        development_date = row.get("Development date")
        if not run_for or not model_name or development_date is None:
            continue
        model_development_dates.setdefault(run_for, {})
        if model_name not in model_development_dates[run_for]:
            model_development_dates[run_for][model_name] = development_date

    workbook_model_names = _ordered_unique_strings(
        transformed_df.get(config.DUMMY_MEV_MODEL_NAME_COLUMN, pd.Series(dtype=object)).tolist()
    )

    segment_values = _ordered_unique_strings(
        transformed_df.get("Segment", pd.Series(dtype=object)).tolist()
    )
    run_for_values = _ordered_unique_strings(
        time_series_df.get("Run For", pd.Series(dtype=object)).tolist()
    )
    transformed_mev_names = {
        value for value in _ordered_unique_strings(
            transformed_df.get("US Mnemonic", pd.Series(dtype=object)).tolist()
        )
        if value
    }
    raw_mev_names = {
        value for value in _ordered_unique_strings(
            raw_df.get("US Mnemonic", pd.Series(dtype=object)).tolist()
        )
        if value
    }

    return {
        "model_names": workbook_model_names or load_saas_model_names(),
        "model_segments": model_segments,
        "model_development_dates": model_development_dates,
        "run_for_quarter_zero_dates": run_for_quarter_zero_dates,
        "model_mev_family_map": model_mev_family_map,
        "model_mev_map": {
            model_name: {
                "transformed": sorted(values.get("transformed", set())),
                "raw": sorted(values.get("raw", set())),
            }
            for model_name, values in model_mev_map.items()
        },
        "segment_values": segment_values,
        "run_for_values": run_for_values,
        "transformed_mev_names": transformed_mev_names,
        "raw_mev_names": raw_mev_names,
        "mev_label_map": mev_label_map,
        "mev_group_label_map": mev_group_label_map,
        "mev_description_map": mev_description_map,
        "mev_time_series": time_series_df,
    }


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
        "mev_catalog": load_pd_mev_catalog(),
        "rank_ordering_facilities": load_pd_rank_ordering_facilities(),
    }
