"""Persistence / source-data loading for the SAAS dashboard.

Loads the dummy MEV workbook (``dummy_mev_data.xlsx``) used by the SAAS
workspace's top filters and MEV time-series chart: model/segment/MEV catalogs,
descriptive label maps, development dates and the cleaned time-series frame.

Feature-private -- only :mod:`features.saas.data_access` reads from this
module. The model-name filter falls back to the monitoring PD MEV catalog
keys when the workbook can't be read (best effort), which is the one place
this module reaches into monitoring's repository.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ....data.analytics import constants as config
from ....data.common.text import normalize_model_name as _normalize_model_name
from ....data.common.text import ordered_unique_strings as _ordered_unique_strings
from ...monitoring.repositories.loader import load_pd_mev_catalog

log = logging.getLogger(__name__)


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
        "model_segments_map": {},
        "model_development_dates": {},
        "run_for_quarter_zero_dates": {},
        "model_mev_family_map": {},
        "segment_values": [],
        "run_for_values": [],
        "mev_label_map": {},
        "mev_group_label_map": {},
        "mev_description_map": {},
        "model_descriptive_name_map": {},
        "model_mev_contribution_map": {},
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
    model_segments_map: dict[str, list[str]] = {}
    model_mev_map: dict[str, dict[str, set[str]]] = {}
    model_mev_family_map: dict[str, dict[str, list[str]]] = {}
    model_mev_contribution_map: dict[str, dict[str, float]] = {}
    for row in transformed_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get(config.DUMMY_MEV_MODEL_NAME_COLUMN))
        segment = str(row.get("Segment") or "").strip()
        transformed_mev_name = str(row.get("US Mnemonic") or "").strip()
        # Source column is misspelled "Model controbution" in the workbook.
        contribution = row.get("Model controbution", row.get("Model contribution"))
        if model_name and transformed_mev_name and contribution is not None:
            try:
                model_mev_contribution_map.setdefault(model_name, {})[transformed_mev_name] = float(contribution)
            except (TypeError, ValueError):
                pass
        raw_mev_names = [
            item.strip()
            for item in str(row.get("SAAS_raw_mnemonic") or "").split(",")
            if item.strip()
        ]
        if model_name and segment and model_name not in model_segments:
            model_segments[model_name] = segment
        if model_name and segment:
            # A model can belong to several segments - keep every distinct one,
            # in order of first appearance.
            segments_for_model = model_segments_map.setdefault(model_name, [])
            if segment not in segments_for_model:
                segments_for_model.append(segment)
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
    model_descriptive_name_map: dict[str, str] = {}
    for row in model_characteristic_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get("Model Name"))
        descriptive_name = str(row.get("Model descriptive name") or "").strip()
        if model_name and descriptive_name and model_name not in model_descriptive_name_map:
            model_descriptive_name_map[model_name] = descriptive_name
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
        "model_segments_map": model_segments_map,
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
        "model_descriptive_name_map": model_descriptive_name_map,
        "model_mev_contribution_map": model_mev_contribution_map,
        "mev_time_series": time_series_df,
    }
