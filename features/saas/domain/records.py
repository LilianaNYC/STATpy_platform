"""Pure SAAS workspace record scoping and filtering helpers."""

from __future__ import annotations

from ..data_access import SAAS_PAGE_DATA
from . import selectors

DEFAULT_SCENARIO_FILTER = selectors.DEFAULT_SCENARIO_FILTER


def coerce_quarter(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def date_period_key(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except TypeError:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    return str(value)


def available_date_periods(records: list[dict]) -> list[str]:
    return sorted({
        date_period_key(row.get("Date"))
        for row in records
        if date_period_key(row.get("Date"))
    })


def normalize_date_range(range_value, periods: list[str]) -> dict[str, str]:
    range_value = range_value or {}
    range_from = range_value.get("from", "")
    range_to = range_value.get("to", "")
    return {
        "from": range_from if range_from in periods else "",
        "to": range_to if range_to in periods else "",
    }


def filter_records_by_snapshot_period(records: list[dict], snapshot_period: str | None) -> list[dict]:
    snapshot_period_value = selectors.normalize_snapshot_period(snapshot_period)
    if snapshot_period_value == selectors.DEFAULT_SUBNAV_VIEW:
        return list(records)

    filtered_records: list[dict] = []
    for row in records:
        quarter_value = coerce_quarter(row.get("Quarter"))
        if quarter_value is None:
            continue
        if snapshot_period_value == "history" and quarter_value <= 0:
            filtered_records.append(row)
        elif snapshot_period_value == "projection" and quarter_value >= 0:
            filtered_records.append(row)
    return filtered_records


def filter_records_by_date_range(records: list[dict], range_value) -> list[dict]:
    periods = available_date_periods(records)
    selection = normalize_date_range(range_value, periods)
    if not selection["from"] and not selection["to"]:
        return list(records)

    filtered_records: list[dict] = []
    for row in records:
        period = date_period_key(row.get("Date"))
        if not period:
            continue
        if selection["from"] and period < selection["from"]:
            continue
        if selection["to"] and period > selection["to"]:
            continue
        filtered_records.append(row)
    return filtered_records


def filter_records_by_scenarios(records: list[dict], selected_scenarios) -> list[dict]:
    normalized_scenarios = selectors.normalize_selected_scenarios(selected_scenarios)
    if not normalized_scenarios:
        return []
    if DEFAULT_SCENARIO_FILTER in normalized_scenarios:
        return records
    selected_scenario_set = set(normalized_scenarios)
    return [row for row in records if str(row.get("Scenario") or "").strip().lower() in selected_scenario_set]


def build_scenario_options(records: list[dict]) -> list[dict]:
    scenario_values: list[str] = []
    seen: set[str] = set()
    for row in records:
        scenario_value = str(row.get("Scenario") or "").strip().lower()
        if not scenario_value or scenario_value in seen:
            continue
        seen.add(scenario_value)
        scenario_values.append(scenario_value)
    return [
        {"label": selectors.format_scenario_label(value), "value": value}
        for value in scenario_values
    ]


def family_map_for_model(model_name: str) -> dict[str, list[str]]:
    return SAAS_PAGE_DATA.get("model_mev_family_map", {}).get(model_name, {})


def allowed_mev_names_for_model(model_name: str, selected_mev_mode: str | None = None) -> set[str]:
    model_mev_map = SAAS_PAGE_DATA.get("model_mev_map", {})
    model_entry = model_mev_map.get(model_name, {})
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode in {"family", "transformed_only"}:
        return set(model_entry.get("transformed", []))
    return set(model_entry.get("raw", []))


def filter_records_by_model_mevs(records: list[dict], model_name: str, selected_mev_mode: str | None = None) -> list[dict]:
    allowed_mev_names = allowed_mev_names_for_model(model_name, selected_mev_mode)
    if not allowed_mev_names:
        return []
    return [
        row for row in records
        if str(row.get("MEV Name") or "").strip() in allowed_mev_names
    ]


def filter_records_by_mevs(records: list[dict], selected_mevs) -> list[dict]:
    selected_mev_values = selectors.normalize_selected_mevs(selected_mevs)
    if not selected_mev_values:
        return []
    selected_mev_set = set(selected_mev_values)
    return [row for row in records if str(row.get("MEV Name") or "").strip() in selected_mev_set]


def records_for_model_scope(model_name: str, run_for, snapshot_period: str | None, compare_against=None) -> list[dict]:
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    if time_series_df is None or time_series_df.empty:
        return []

    selected_run_fors = selectors.scoped_run_for_values(run_for, compare_against)
    filtered_df = time_series_df[time_series_df["Model Name"] == model_name]
    if selected_run_fors:
        filtered_df = filtered_df[filtered_df["Run For"].isin(selected_run_fors)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    return filter_records_by_snapshot_period(
        filtered_df.to_dict(orient="records"),
        selectors.normalize_snapshot_period(snapshot_period),
    )


def build_model_mev_options(records: list[dict], label_mode: str | None) -> list[dict]:
    mev_names = sorted(
        {str(row.get("MEV Name") or "").strip() for row in records if str(row.get("MEV Name") or "").strip()},
        key=lambda value: selectors.resolve_mev_label(value, label_mode).lower(),
    )
    options: list[dict] = []
    for mev_name in mev_names:
        options.append({"label": selectors.resolve_mev_label(mev_name, label_mode), "value": mev_name})
    return options


def build_model_mev_options_for_mode(
    model_name: str,
    run_for,
    snapshot_period: str | None,
    mev_label_mode: str | None,
    selected_mev_mode: str | None,
    compare_against=None,
) -> list[dict]:
    base_records = records_for_model_scope(model_name, run_for, snapshot_period, compare_against)
    return build_model_mev_options(
        filter_records_by_model_mevs(base_records, model_name, selected_mev_mode),
        mev_label_mode,
    )


def family_display_mevs(model_name: str, selected_mev: str | None, records: list[dict] | None = None) -> list[str]:
    available_names = {
        str(row.get("MEV Name") or "").strip()
        for row in (records or [])
        if str(row.get("MEV Name") or "").strip()
    }
    family_map = family_map_for_model(model_name)
    normalized_selected = str(selected_mev or "").strip()
    if not normalized_selected:
        return []

    family_values = [normalized_selected]
    family_values.extend(family_map.get(normalized_selected, []))
    ordered_values = list(dict.fromkeys(value for value in family_values if value))
    if not available_names:
        return ordered_values
    return [value for value in ordered_values if value in available_names]


def active_selected_mevs(
    model_name: str,
    selected_mev_mode: str | None,
    selected_mev_single,
    selected_mevs_multi,
    records: list[dict] | None = None,
) -> list[str]:
    normalized_mode = selectors.normalize_selected_mev_mode(selected_mev_mode)
    if normalized_mode == "family":
        selected_value = selectors.normalize_selected_mevs(selected_mev_single)
        selected_mev = selected_value[0] if selected_value else None
        return family_display_mevs(model_name, selected_mev, records)
    return selectors.normalize_selected_mevs(selected_mevs_multi)
