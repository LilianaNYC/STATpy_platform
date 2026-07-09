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
    segment_values = _ordered_unique_strings(
        model_characteristic_df.get("Segment Name", pd.Series(dtype=object)).tolist()
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


    # def load_saas_mev_workbook_data_v2() -> dict[str, Any]:
    #     """Load the SAAS workbook data used by the top filters and MEV chart."""
    #     empty_time_series = pd.DataFrame(
    #         columns=["Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value", "Model Name"]
    #     )
    #     payload = {
    #         "model_names": [],
    #         "model_segments": {},
    #         "model_segments_map": {},
    #         "model_development_dates": {},
    #         "run_for_quarter_zero_dates": {},
    #         "model_mev_family_map": {},
    #         "segment_values": [],
    #         "run_for_values": [],
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
    #         mev_trans = get_sql_data("STAT_Config", query_trans)
    #         print(f"Loaded [dbo].[mev_transformed] from STAT_Config. Rows: {len(mev_trans)}")
    #     except Exception as error:
    #         print(f"Failed to load [dbo].[mev_transformed] from STAT_Config: {error}")

    #     try:
    #         mev_raw = get_sql_data("STAT_Config", query_raw)
    #         print(f"Loaded [dbo].[mev_raw] from STAT_Config. Rows: {len(mev_raw)}")
    #     except Exception as error:
    #         print(f"Failed to load [dbo].[mev_raw] from STAT_Config: {error}")

    #     try:
    #         model_names = get_sql_data("STAT_Config", query_model_names)
    #         model_names = model_names[["Run For", "Segment Name", "Model Name", "Development Date"]].drop_duplicates()
    #         print(f"Loaded [dbo].[model_names] from STAT_Config. Rows: {len(model_names)}")
    #     except Exception as error:
    #         print(f"Failed to load [dbo].[model_names] from STAT_Config: {error}")

    #     try:
    #         run_details = get_sql_data("STAT_Config", query_run_details)
    #         run_details = run_details[run_details["Status"] == "Y"][["Run For"]].drop_duplicates()
    #         print(f"Loaded [dbo].[run_details] from STAT_Config. Rows: {len(run_details)}")
    #         print(run_details)
    #     except Exception as error:
    #         print(f"Failed to load [dbo].[run_details] from STAT_Config: {error}")

    #     mev_time_series = pd.DataFrame()
    #     for run_for in run_details["Run For"]:
    #         try:
    #             db_name = f"STAT_Inputs_{run_for.replace(' ', '_')}_BHC"
    #             time_series = get_sql_data(db_name, query_mev_time_series)
    #             mev_time_series = pd.concat([mev_time_series, time_series], ignore_index=True)
    #         except Exception as error:
    #             print(f"Failed to load [input].[scenario] from {db_name}: {error}")

    #     mev_trans["Model Name"] = mev_trans["Model Name"].str.upper()
    #     model_names["Model Name"] = model_names["Model Name"].str.upper()
    #     model_names["Development Date"] = pd.to_datetime(model_names["Development Date"], errors="coerce")
    #     mev_time_series["Date"] = pd.to_datetime(mev_time_series["Date"], errors="coerce")
    #     mev_time_series["MEV Name"] = mev_time_series["MEV Name"].astype(str).str.replace(r'^"+|"+$', "", regex=True)

    #     payload["model_names"] = model_names["Model Name"].unique().tolist()  # ok
    #     # model_segments_map holds every distinct segment per model (order of
    #     # first appearance); model_segments holds just the first one -- callers
    #     # like selectors.py compare model_segments.get(model_name) == segment,
    #     # so it must stay a single string, not the same list as _map.
    #     model_segments_map = model_names.groupby("Model Name")["Segment Name"].apply(
    #         lambda values: list(dict.fromkeys(values.dropna()))
    #     ).to_dict()
    #     payload["model_segments_map"] = model_segments_map
    #     payload["model_segments"] = {
    #         model_name: segments[0] for model_name, segments in model_segments_map.items() if segments
    #     }
    #     payload["model_development_dates"] = model_names.groupby("Run For").apply(
    #         lambda g: g.set_index("Model Name")["Development Date"].to_dict()
    #     ).to_dict()  # ok
    #     payload["run_for_quarter_zero_dates"] = run_for_to_year_end(run_details["Run For"].tolist())
    #     payload["model_mev_family_map"] = mev_trans.groupby("Model Name").apply(
    #         lambda g: g.set_index("US Mnemonic")["SAAS_raw_mnemonic"]
    #         .apply(lambda s: [x.strip() for x in str(s).split(",") if x.strip()])
    #         .to_dict()
    #     ).to_dict()  # ok

    #     payload["model_mev_map"] = mev_trans.groupby("Model Name").apply(
    #         lambda g: {
    #             "transformed": g["US Mnemonic"].drop_duplicates().tolist(),
    #             "raw": pd.unique(g["SAAS_raw_mnemonic"].astype(str).str.split(",").explode().str.strip()).tolist(),
    #         }
    #     ).to_dict()  # ok

    #     payload["segment_values"] = model_names["Segment Name"].dropna().unique().tolist()  # ok
    #     payload["run_for_values"] = run_details["Run For"].tolist()  # ok
    #     payload["transformed_mev_names"] = set(mev_trans["US Mnemonic"])  # ok
    #     payload["raw_mev_names"] = set(mev_raw["US Mnemonic"])  # ok
    #     payload["mev_label_map"] = mev_trans.drop_duplicates("US Mnemonic").set_index("US Mnemonic")["Long Name"].to_dict()  # ok
    #     payload["mev_group_label_map"] = mev_raw.drop_duplicates("US Mnemonic").set_index("US Mnemonic")["Group Mnemonic"].to_dict()  # ok
    #     payload["mev_description_map"] = mev_trans.drop_duplicates("US Mnemonic").set_index("US Mnemonic")["Description"].to_dict()  # ok
    #     payload["model_descriptive_name_map"] = {m: m for m in model_names["Model Name"].dropna().unique()}
    #     payload["model_mev_contribution_map"] = {}

    #     mev_time_series = mev_time_series.drop(columns=["Model Name"], errors="ignore")
    #     model_mev_sets_map = {
    #         model_name: {"transformed": set(mevs["transformed"]), "raw": set(mevs["raw"])}
    #         for model_name, mevs in payload["model_mev_map"].items()
    #     }
    #     mev_time_series = _attribute_mev_rows_to_models(mev_time_series, model_mev_sets_map)
    #     payload["mev_time_series"] = mev_time_series  # ok

    #     return payload
