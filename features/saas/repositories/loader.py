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

from ....shared.domain import constants as config
from ....config.settings import settings
from ....shared.text import normalize_model_name as _normalize_model_name
from ....shared.text import ordered_unique_strings as _ordered_unique_strings
from ...monitoring.repositories.loader import load_pd_mev_catalog

log = logging.getLogger(__name__)


def load_saas_model_names() -> list[str]:
    """Load SAAS model-name filter options from the dummy MEV workbook."""
    try:
        df = pd.read_excel(
            settings.dummy_mev_data_file,
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
            settings.dummy_mev_data_file,
            config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort loading keeps the page available
        log.warning(
            "Unable to load SAAS model names from %s [%s]: %s",
            settings.dummy_mev_data_file,
            config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
            exc,
        )

    return list(load_pd_mev_catalog().keys())


def _attribute_mev_rows_to_models(
    time_series_df: pd.DataFrame,
    model_mev_map: dict[str, dict[str, set[str]]],
) -> pd.DataFrame:
    """Derive each row's owning model(s) and explode rows shared across models.

    ``scenario``'s own ``Model Name`` column is unreliable and intentionally
    *not* read here -- the column may still exist in the workbook (kept for
    other purposes outside the app), but per-row model attribution is always
    derived from ``model_mev_map`` (built from the reliable
    ``mev_transformed`` sheet) instead. A MEV can belong to more
    than one model, so a row whose MEV is shared is duplicated once per
    owning model; a row whose MEV isn't claimed by any model is dropped.
    """
    mev_name_to_models: dict[str, set[str]] = {}
    for model_name, mev_sets in model_mev_map.items():
        for mev_name in mev_sets["transformed"] | mev_sets["raw"]:
            mev_name_to_models.setdefault(mev_name, set()).add(model_name)

    time_series_df = time_series_df.copy()
    time_series_df["Model Name"] = time_series_df["MEV Name"].map(
        lambda name: sorted(mev_name_to_models.get(name, ()))
    )
    time_series_df = time_series_df[time_series_df["Model Name"].map(bool)]
    return time_series_df.explode("Model Name", ignore_index=True)


def load_saas_mev_workbook_data() -> dict[str, Any]:
    """Load the SAAS workbook data used by the top filters and MEV chart."""
    empty_time_series = pd.DataFrame(
        columns=["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value", "Model Name"]
    )
    empty_payload = {
        "model_names": load_saas_model_names(),
        "model_segments": {},
        "model_segments_map": {},
        "model_region_map": {},
        "model_group_map": {},
        "model_portfolio_map": {},
        "model_development_dates": {},
        "run_for_quarter_zero_dates": {},
        "model_mev_family_map": {},
        "model_mev_map": {},
        "segment_values": [],
        "region_values": [],
        "model_group_values": [],
        "portfolio_values": [],
        "run_for_values": [],
        "transformed_mev_names": set(),
        "raw_mev_names": set(),
        "mev_label_map": {},
        "mev_group_label_map": {},
        "mev_description_map": {},
        "model_descriptive_name_map": {},
        "descriptive_groups": {},
        "model_mev_contribution_map": {},
        "mev_time_series": empty_time_series,
    }

    try:
        transformed_df = pd.read_excel(
            settings.dummy_mev_data_file,
            sheet_name=config.DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME,
        )
        raw_df = pd.read_excel(
            settings.dummy_mev_data_file,
            sheet_name=config.DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME,
        )
        time_series_df = pd.read_excel(
            settings.dummy_mev_data_file,
            sheet_name=config.DUMMY_MEV_TIME_SERIES_SHEET_NAME,
        )
        model_characteristic_df = pd.read_excel(
            settings.dummy_mev_data_file,
            sheet_name=config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - keep the page available if workbook loading fails
        log.warning("Unable to load SAAS MEV workbook data from %s: %s", settings.dummy_mev_data_file, exc)
        return empty_payload

    transformed_df = transformed_df.where(pd.notna(transformed_df), None)
    raw_df = raw_df.where(pd.notna(raw_df), None)
    time_series_df = time_series_df.where(pd.notna(time_series_df), None)
    model_characteristic_df = model_characteristic_df.where(pd.notna(model_characteristic_df), None)

    model_mev_map: dict[str, dict[str, set[str]]] = {}
    model_mev_family_map: dict[str, dict[str, list[str]]] = {}
    model_mev_contribution_map: dict[str, dict[str, float]] = {}
    for row in transformed_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get(config.DUMMY_MEV_MODEL_NAME_COLUMN))
        transformed_mev_name = str(row.get("US Mnemonic") or "").strip()
        contribution = row.get("Model Contribution")
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
    time_series_df["MEV Value"] = pd.to_numeric(time_series_df.get("MEV Value"), errors="coerce")
    time_series_df = time_series_df.dropna(subset=["Date", "MEV Value"])
    time_series_df = time_series_df[time_series_df["MEV Name"].astype(bool)][
        ["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value"]
    ].copy()
    time_series_df = _attribute_mev_rows_to_models(time_series_df, model_mev_map)

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
    model_segments: dict[str, str] = {}
    model_segments_map: dict[str, list[str]] = {}
    model_region_map: dict[str, list[str]] = {}
    model_group_map: dict[str, list[str]] = {}
    model_portfolio_map: dict[str, list[str]] = {}
    for row in model_characteristic_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get("Model Name"))
        descriptive_name = str(row.get("Model Descriptive Name") or "").strip()
        if model_name and descriptive_name and model_name not in model_descriptive_name_map:
            model_descriptive_name_map[model_name] = descriptive_name
        segment = str(row.get("Segment Name") or "").strip()
        if model_name and segment:
            if model_name not in model_segments:
                model_segments[model_name] = segment
            # A model can belong to several segments - keep every distinct one,
            # in order of first appearance.
            segments_for_model = model_segments_map.setdefault(model_name, [])
            if segment not in segments_for_model:
                segments_for_model.append(segment)
        region = str(row.get("Region") or "").strip()
        if model_name and region:
            regions_for_model = model_region_map.setdefault(model_name, [])
            if region not in regions_for_model:
                regions_for_model.append(region)
        model_group = str(row.get("Model Type") or "").strip()
        if model_name and model_group:
            groups_for_model = model_group_map.setdefault(model_name, [])
            if model_group not in groups_for_model:
                groups_for_model.append(model_group)
        portfolio = str(row.get("Portfolio") or "").strip()
        if model_name and portfolio:
            portfolios_for_model = model_portfolio_map.setdefault(model_name, [])
            if portfolio not in portfolios_for_model:
                portfolios_for_model.append(portfolio)
    # Parent (Model Descriptive Name) -> ordered child Model Names. Model Name is
    # the only unique id, so a model with no descriptive name is its own singleton
    # parent -- this is the single place the "fall back to Model Name" rule is
    # applied (mirrors selectors.model_descriptive_label). Two Model Names sharing
    # a descriptive name are the intended children of one parent.
    descriptive_groups: dict[str, list[str]] = {}
    for row in model_characteristic_df.to_dict(orient="records"):
        model_name = _normalize_model_name(row.get("Model Name"))
        if not model_name:
            continue
        parent = model_descriptive_name_map.get(model_name) or model_name
        members = descriptive_groups.setdefault(parent, [])
        if model_name not in members:
            members.append(model_name)

    segment_values = _ordered_unique_strings(
        model_characteristic_df.get("Segment Name", pd.Series(dtype=object)).tolist()
    )
    region_values = _ordered_unique_strings(
        model_characteristic_df.get("Region", pd.Series(dtype=object)).tolist()
    )
    model_group_values = _ordered_unique_strings(
        model_characteristic_df.get("Model Type", pd.Series(dtype=object)).tolist()
    )
    portfolio_values = _ordered_unique_strings(
        model_characteristic_df.get("Portfolio", pd.Series(dtype=object)).tolist()
    )
    model_characteristic_df["Development Date"] = pd.to_datetime(
        model_characteristic_df.get("Development Date"),
        dayfirst=False,
        errors="coerce",
    )
    model_characteristic_df = model_characteristic_df.dropna(subset=["Development Date"])
    model_development_dates: dict[str, dict[str, Any]] = {}
    for row in model_characteristic_df.to_dict(orient="records"):
        run_for = str(row.get("Run For") or "").strip()
        model_name = _normalize_model_name(row.get("Model Name"))
        development_date = row.get("Development Date")
        if not run_for or not model_name or development_date is None:
            continue
        model_development_dates.setdefault(run_for, {})
        if model_name not in model_development_dates[run_for]:
            model_development_dates[run_for][model_name] = development_date

    workbook_model_names = _ordered_unique_strings(
        transformed_df.get(config.DUMMY_MEV_MODEL_NAME_COLUMN, pd.Series(dtype=object)).tolist()
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
        "model_region_map": model_region_map,
        "model_group_map": model_group_map,
        "model_portfolio_map": model_portfolio_map,
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
        "region_values": region_values,
        "model_group_values": model_group_values,
        "portfolio_values": portfolio_values,
        "run_for_values": run_for_values,
        "transformed_mev_names": transformed_mev_names,
        "raw_mev_names": raw_mev_names,
        "mev_label_map": mev_label_map,
        "mev_group_label_map": mev_group_label_map,
        "mev_description_map": mev_description_map,
        "model_descriptive_name_map": model_descriptive_name_map,
        "descriptive_groups": descriptive_groups,
        "model_mev_contribution_map": model_mev_contribution_map,
        "mev_time_series": time_series_df,
    }


# def load_saas_mev_workbook_data() -> dict[str, Any]:
#     """Load the SAAS MEV data used by the top filters and MEV chart from SQL.

#     Reads model/MEV catalogs from ``STAT_Config`` (``mev_transformed``,
#     ``mev_raw``, ``model_names``, ``run_details``) and the per-cycle scenario
#     time series from each active Run For's own ``STAT_Inputs_<cycle>_BHC``
#     database (``input.scenario``). Active cycles are those with
#     ``run_details.Status == "Y"``.
#     """
#     empty_time_series = pd.DataFrame(
#         columns=["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value", "Model Name"]
#     )
#     empty_payload = {
#         "model_names": load_saas_model_names(),
#         "model_segments": {},
#         "model_segments_map": {},
#         "model_region_map": {},
#         "model_group_map": {},
#         "model_portfolio_map": {},                 # NEW
#         "model_development_dates": {},
#         "run_for_quarter_zero_dates": {},
#         "model_mev_family_map": {},
#         "model_mev_map": {},
#         "segment_values": [],
#         "region_values": [],
#         "model_group_values": [],
#         "portfolio_values": [],                    # NEW
#         "run_for_values": [],
#         "transformed_mev_names": set(),
#         "raw_mev_names": set(),
#         "mev_label_map": {},
#         "mev_group_label_map": {},
#         "mev_description_map": {},
#         "model_descriptive_name_map": {},
#         "model_mev_contribution_map": {},
#         "mev_time_series": empty_time_series,
#     }

#     query_trans = "SELECT * FROM [dbo].[mev_transformed]"
#     query_raw = "SELECT * FROM [dbo].[mev_raw]"
#     query_model_names = "SELECT * FROM [dbo].[model_names]"
#     query_run_details = "SELECT * FROM [dbo].[run_details]"
#     query_mev_time_series = "SELECT * FROM [input].[scenario]"

#     try:
#         transformed_df = get_sql_data("STAT_Config", query_trans)
#         log.info("Loaded [dbo].[mev_transformed] from STAT_Config. Rows: %s", len(transformed_df))
#     except Exception as exc:  # noqa: BLE001 - keep the page available if the DB can't be read
#         log.warning("Failed to load [dbo].[mev_transformed] from STAT_Config: %s", exc)
#         return empty_payload

#     try:
#         raw_df = get_sql_data("STAT_Config", query_raw)
#         log.info("Loaded [dbo].[mev_raw] from STAT_Config. Rows: %s", len(raw_df))
#     except Exception as exc:  # noqa: BLE001
#         log.warning("Failed to load [dbo].[mev_raw] from STAT_Config: %s", exc)
#         return empty_payload

#     try:
#         model_characteristic_df = get_sql_data("STAT_Config", query_model_names)
#         model_characteristic_df = model_characteristic_df[
#             [
#                 "Run For",
#                 "Segment Name",
#                 "Model Name",
#                 "Development Date",
#                 "Model Descriptive Name",
#                 "Region",
#                 "Model Type",
#                 "Portfolio",                        # NEW
#             ]
#         ].drop_duplicates()
#         log.info("Loaded [dbo].[model_names] from STAT_Config. Rows: %s", len(model_characteristic_df))
#     except Exception as exc:  # noqa: BLE001
#         log.warning("Failed to load [dbo].[model_names] from STAT_Config: %s", exc)
#         return empty_payload

#     try:
#         run_details_df = get_sql_data("STAT_Config", query_run_details)
#         run_details_df = run_details_df[run_details_df["Status"] == "Y"][["Run For"]].drop_duplicates()
#         log.info("Loaded [dbo].[run_details] from STAT_Config. Rows: %s", len(run_details_df))
#     except Exception as exc:  # noqa: BLE001
#         log.warning("Failed to load [dbo].[run_details] from STAT_Config: %s", exc)
#         return empty_payload

#     active_run_fors = [
#         str(value).strip() for value in run_details_df.get("Run For", pd.Series(dtype=object)).tolist()
#         if str(value).strip()
#     ]

#     time_series_frames: list[pd.DataFrame] = []
#     for run_for in active_run_fors:
#         db_name = f"STAT_Inputs_{run_for.replace(' ', '_')}_BHC"
#         try:
#             cycle_df = get_sql_data(db_name, query_mev_time_series)
#             time_series_frames.append(cycle_df)
#         except Exception as exc:  # noqa: BLE001 - one cycle's DB being unavailable shouldn't blank the rest
#             log.warning("Failed to load [input].[scenario] from %s: %s", db_name, exc)

#     time_series_df = (
#         pd.concat(time_series_frames, ignore_index=True)
#         if time_series_frames
#         else empty_time_series.drop(columns=["Model Name"])
#     )

#     transformed_df = transformed_df.where(pd.notna(transformed_df), None)
#     raw_df = raw_df.where(pd.notna(raw_df), None)
#     model_characteristic_df = model_characteristic_df.where(pd.notna(model_characteristic_df), None)

#     model_mev_map: dict[str, dict[str, set[str]]] = {}
#     model_mev_family_map: dict[str, dict[str, list[str]]] = {}
#     model_mev_contribution_map: dict[str, dict[str, float]] = {}
#     for row in transformed_df.to_dict(orient="records"):
#         model_name = _normalize_model_name(row.get(config.DUMMY_MEV_MODEL_NAME_COLUMN))
#         transformed_mev_name = str(row.get("US Mnemonic") or "").strip()
#         contribution = row.get("Model Contribution")
#         if model_name and transformed_mev_name and contribution is not None:
#             try:
#                 model_mev_contribution_map.setdefault(model_name, {})[transformed_mev_name] = float(contribution)
#             except (TypeError, ValueError):
#                 pass
#         raw_mev_names = [
#             item.strip()
#             for item in str(row.get("SAAS_raw_mnemonic") or "").split(",")
#             if item.strip()
#         ]
#         if model_name:
#             model_mev_map.setdefault(model_name, {"transformed": set(), "raw": set()})
#             if transformed_mev_name:
#                 model_mev_map[model_name]["transformed"].add(transformed_mev_name)
#                 model_mev_family_map.setdefault(model_name, {})
#                 if transformed_mev_name not in model_mev_family_map[model_name]:
#                     model_mev_family_map[model_name][transformed_mev_name] = list(dict.fromkeys(raw_mev_names))
#             if raw_mev_names:
#                 model_mev_map[model_name]["raw"].update(raw_mev_names)

#     mev_label_map: dict[str, str] = {}
#     mev_group_label_map: dict[str, str] = {}
#     mev_description_map: dict[str, str] = {}
#     for description_df in (transformed_df, raw_df):
#         for row in description_df.to_dict(orient="records"):
#             mev_name = str(row.get("US Mnemonic") or "").strip()
#             long_name = str(row.get("Long Name") or "").strip()
#             description = str(row.get("Description") or "").strip()
#             if mev_name and long_name and mev_name not in mev_label_map:
#                 mev_label_map[mev_name] = long_name
#             if mev_name and description and mev_name not in mev_description_map:
#                 mev_description_map[mev_name] = description
#     for row in raw_df.to_dict(orient="records"):
#         mev_name = str(row.get("US Mnemonic") or "").strip()
#         group_mnemonic = str(row.get("Group Mnemonic") or "").strip()
#         if mev_name and group_mnemonic and mev_name not in mev_group_label_map:
#             mev_group_label_map[mev_name] = group_mnemonic

#     time_series_df["Date"] = pd.to_datetime(time_series_df.get("Date"), dayfirst=False, errors="coerce")
#     time_series_df["Quarter"] = pd.to_numeric(time_series_df.get("Quarter"), errors="coerce")
#     time_series_df["Run For"] = time_series_df.get("Run For").map(lambda value: str(value).strip() if value is not None else "")
#     time_series_df["Scenario"] = time_series_df.get("Scenario").map(lambda value: str(value).strip() if value is not None else "")
#     time_series_df["MEV Name"] = time_series_df.get("MEV Name").map(lambda value: str(value).strip() if value is not None else "")
#     time_series_df["MEV Value"] = pd.to_numeric(time_series_df.get("MEV Value"), errors="coerce")
#     time_series_df = time_series_df.dropna(subset=["Date", "MEV Value"])
#     time_series_df = time_series_df[time_series_df["MEV Name"].astype(bool)][
#         ["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value"]
#     ].copy()
#     time_series_df = _attribute_mev_rows_to_models(time_series_df, model_mev_map)

#     run_for_quarter_zero_dates: dict[str, Any] = {}
#     quarter_zero_df = time_series_df[time_series_df["Quarter"] == 0]
#     for row in quarter_zero_df.to_dict(orient="records"):
#         run_for = str(row.get("Run For") or "").strip()
#         date_value = row.get("Date")
#         if not run_for or date_value is None:
#             continue
#         if run_for not in run_for_quarter_zero_dates or date_value < run_for_quarter_zero_dates[run_for]:
#             run_for_quarter_zero_dates[run_for] = date_value

#     model_characteristic_df["Run For"] = model_characteristic_df.get("Run For").map(
#         lambda value: str(value).strip() if value is not None else ""
#     )
#     model_characteristic_df["Model Name"] = model_characteristic_df.get("Model Name").map(_normalize_model_name)

#     model_descriptive_name_map: dict[str, str] = {}
#     model_segments: dict[str, str] = {}
#     model_segments_map: dict[str, list[str]] = {}
#     model_region_map: dict[str, list[str]] = {}
#     model_group_map: dict[str, list[str]] = {}
#     model_portfolio_map: dict[str, list[str]] = {}     # NEW
#     for row in model_characteristic_df.to_dict(orient="records"):
#         model_name = row.get("Model Name")
#         descriptive_name = str(row.get("Model Descriptive Name") or "").strip()
#         if model_name and descriptive_name and model_name not in model_descriptive_name_map:
#             model_descriptive_name_map[model_name] = descriptive_name
#         segment = str(row.get("Segment Name") or "").strip()
#         if model_name and segment:
#             if model_name not in model_segments:
#                 model_segments[model_name] = segment
#             # A model can belong to several segments - keep every distinct one,
#             # in order of first appearance.
#             segments_for_model = model_segments_map.setdefault(model_name, [])
#             if segment not in segments_for_model:
#                 segments_for_model.append(segment)
#         region = str(row.get("Region") or "").strip()
#         if model_name and region:
#             regions_for_model = model_region_map.setdefault(model_name, [])
#             if region not in regions_for_model:
#                 regions_for_model.append(region)
#         model_group = str(row.get("Model Type") or "").strip()
#         if model_name and model_group:
#             groups_for_model = model_group_map.setdefault(model_name, [])
#             if model_group not in groups_for_model:
#                 groups_for_model.append(model_group)
#         portfolio = str(row.get("Portfolio") or "").strip()                    # NEW
#         if model_name and portfolio:                                           # NEW
#             portfolios_for_model = model_portfolio_map.setdefault(model_name, [])  # NEW
#             if portfolio not in portfolios_for_model:                          # NEW
#                 portfolios_for_model.append(portfolio)                         # NEW
#     segment_values = _ordered_unique_strings(
#         model_characteristic_df.get("Segment Name", pd.Series(dtype=object)).tolist()
#     )
#     region_values = _ordered_unique_strings(
#         model_characteristic_df.get("Region", pd.Series(dtype=object)).tolist()
#     )
#     model_group_values = _ordered_unique_strings(
#         model_characteristic_df.get("Model Type", pd.Series(dtype=object)).tolist()
#     )
#     portfolio_values = _ordered_unique_strings(                                # NEW
#         model_characteristic_df.get("Portfolio", pd.Series(dtype=object)).tolist()  # NEW
#     )                                                                          # NEW

#     model_characteristic_df["Development Date"] = pd.to_datetime(
#         model_characteristic_df.get("Development Date"),
#         dayfirst=False,
#         errors="coerce",
#     )
#     model_characteristic_df = model_characteristic_df.dropna(subset=["Development Date"])
#     model_development_dates: dict[str, dict[str, Any]] = {}
#     for row in model_characteristic_df.to_dict(orient="records"):
#         run_for = str(row.get("Run For") or "").strip()
#         model_name = row.get("Model Name")
#         development_date = row.get("Development Date")
#         if not run_for or not model_name or development_date is None:
#             continue
#         model_development_dates.setdefault(run_for, {})
#         if model_name not in model_development_dates[run_for]:
#             model_development_dates[run_for][model_name] = development_date

#     workbook_model_names = _ordered_unique_strings(
#         transformed_df.get(config.DUMMY_MEV_MODEL_NAME_COLUMN, pd.Series(dtype=object)).tolist()
#     )
#     run_for_values = _ordered_unique_strings(
#         time_series_df.get("Run For", pd.Series(dtype=object)).tolist()
#     )
#     transformed_mev_names = {
#         value for value in _ordered_unique_strings(
#             transformed_df.get("US Mnemonic", pd.Series(dtype=object)).tolist()
#         )
#         if value
#     }
#     raw_mev_names = {
#         value for value in _ordered_unique_strings(
#             raw_df.get("US Mnemonic", pd.Series(dtype=object)).tolist()
#         )
#         if value
#     }

#     return {
#         "model_names": workbook_model_names or load_saas_model_names(),
#         "model_segments": model_segments,
#         "model_segments_map": model_segments_map,
#         "model_region_map": model_region_map,
#         "model_group_map": model_group_map,
#         "model_portfolio_map": model_portfolio_map,        # NEW
#         "model_development_dates": model_development_dates,
#         "run_for_quarter_zero_dates": run_for_quarter_zero_dates,
#         "model_mev_family_map": model_mev_family_map,
#         "model_mev_map": {
#             model_name: {
#                 "transformed": sorted(values.get("transformed", set())),
#                 "raw": sorted(values.get("raw", set())),
#             }
#             for model_name, values in model_mev_map.items()
#         },
#         "segment_values": segment_values,
#         "region_values": region_values,
#         "model_group_values": model_group_values,
#         "portfolio_values": portfolio_values,              # NEW
#         "run_for_values": run_for_values,
#         "transformed_mev_names": transformed_mev_names,
#         "raw_mev_names": raw_mev_names,
#         "mev_label_map": mev_label_map,
#         "mev_group_label_map": mev_group_label_map,
#         "mev_description_map": mev_description_map,
#         "model_descriptive_name_map": model_descriptive_name_map,
#         "model_mev_contribution_map": model_mev_contribution_map,
#         "mev_time_series": time_series_df,
#     }


